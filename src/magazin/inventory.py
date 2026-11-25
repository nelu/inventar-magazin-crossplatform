"""PC component inventory and persistence for the CLI's unquoted CSV format."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from tempfile import NamedTemporaryFile


_HEADER = "cod;pret;marca;an;garantie;producator;tara;categorie;stoc"
_INT_MAX = 2**31 - 1  # main.cpp uses stoi for all integer columns.
_MAX_PRICE = Decimal.from_float(sys.float_info.max)
_CENT = Decimal("0.01")


def _integer(name: str, value: int, minimum: int, maximum: int = _INT_MAX) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name}: valoare intre {minimum} si {maximum} asteptata")
    return value


@dataclass(frozen=True)
class Product:
    cod: str
    pret: Decimal
    marca: str
    an: int
    garantie: int
    producator: str
    tara: str
    categorie: str
    stoc: int

    def __post_init__(self) -> None:
        for name in ("cod", "marca", "producator", "tara", "categorie"):
            value = getattr(self, name)
            if not isinstance(value, str) or any(c in value for c in ";\r\n"):
                raise ValueError(f"{name}: camp CSV invalid")
            value = value.strip(" \t")
            if not value:
                raise ValueError(f"{name}: camp gol")
            object.__setattr__(self, name, value)
        _integer("an", self.an, 1980, 2026)
        _integer("garantie", self.garantie, 0)
        _integer("stoc", self.stoc, 0)
        if (not isinstance(self.pret, Decimal) or not self.pret.is_finite()
                or not 0 <= self.pret <= _MAX_PRICE):
            raise ValueError("pret invalid")
        # Keep the stored price identical to the two-decimal export, even on reload.
        with localcontext() as ctx:
            ctx.prec = 312
            price = self.pret.quantize(_CENT, rounding=ROUND_HALF_EVEN)
        object.__setattr__(self, "pret", price.copy_abs())

    @classmethod
    def _from_fields(cls, fields: list[str]) -> Product:
        if len(fields) != 9:
            raise ValueError("numar invalid de campuri (asteptat 9)")
        cod, pret, marca, an, garantie, producator, tara, categorie, stoc = fields
        if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", pret):
            raise ValueError("pret invalid")
        if not all(re.fullmatch(r"[+-]?[0-9]+", n) for n in (an, garantie, stoc)):
            raise ValueError("an, garantie sau stoc invalid")
        try:
            price = Decimal(pret)
        except InvalidOperation as exc:
            raise ValueError("pret invalid") from exc
        return cls(cod, price, marca, int(an), int(garantie), producator, tara, categorie, int(stoc))

    def _row(self) -> str:
        return (f"{self.cod};{self.pret:.2f};{self.marca};{self.an};{self.garantie};"
                f"{self.producator};{self.tara};{self.categorie};{self.stoc}\n")


class Inventory:
    def __init__(self) -> None:
        self._path: Path | None = None
        self._items: dict[str, Product] = {}

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def products(self) -> tuple[Product, ...]:
        return tuple(self._items.values())

    def load(self, path: str | Path) -> list[str]:
        source = Path(path)
        items: dict[str, Product] = {}
        warnings: list[str] = []
        first = True
        with source.open("rb") as stream:
            for n, raw in enumerate(stream, start=1):
                try:
                    line = raw.decode("utf-8-sig" if n == 1 else "utf-8").removesuffix("\n").removesuffix("\r")
                    if not line.strip(" \t"):
                        continue
                    fields = [field.strip(" \t") for field in line.split(";")]
                    if first and fields[0].lower() in ("cod", "cod_produs"):
                        first = False
                        continue
                    item = Product._from_fields(fields)
                    if item.cod in items:
                        raise ValueError(f"cod duplicat {item.cod}")
                    items[item.cod] = item
                except ValueError as exc:
                    warnings.append(f"Linia {n}: {exc}")
                first = False
        self._items, self._path = items, source
        return warnings

    def _persist(self, path: Path, items: dict[str, Product]) -> None:
        tmp: Path | None = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                    dir=path.parent, delete=False) as stream:
                tmp = Path(stream.name)
                stream.write(_HEADER + "\n")
                stream.writelines(item._row() for item in items.values())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        self._items, self._path = items, path

    def save_as(self, path: str | Path) -> None:
        self._persist(Path(path), self._items)

    def _current_path(self) -> Path:
        if self._path is None:
            raise ValueError("Alegeti mai intai fisierul de inventar.")
        return self._path

    def _product(self, cod: str) -> Product:
        if not isinstance(cod, str):
            raise ValueError("Cod invalid")
        try:
            return self._items[cod.strip(" \t")]
        except KeyError:
            raise ValueError(f"Cod inexistent: {cod}") from None

    def add(self, product: Product) -> None:
        path = self._current_path()
        if not isinstance(product, Product):
            raise ValueError("Produs invalid")
        if product.cod in self._items:
            raise ValueError(f"Cod duplicat: {product.cod}")
        self._persist(path, self._items | {product.cod: product})

    def sell(self, cod: str) -> None:
        path = self._current_path()
        item = self._product(cod)
        if item.stoc == 0:
            raise ValueError("Produs epuizat")
        self._persist(path, self._items | {item.cod: replace(item, stoc=item.stoc - 1)})

    def restock(self, cod: str, quantity: int) -> None:
        path = self._current_path()
        item = self._product(cod)
        _integer("cantitate", quantity, 1)
        self._persist(path, self._items | {item.cod: replace(item, stoc=item.stoc + quantity)})

    def delete(self, cod: str) -> None:
        path = self._current_path()
        item = self._product(cod)
        items = self._items.copy()
        del items[item.cod]
        self._persist(path, items)

    def total(self, categorie: str) -> Decimal:
        categorie = categorie.strip(" \t")
        with localcontext() as ctx:
            # 309 price digits + cents + 10 stock digits, plus room for the sum.
            ctx.prec = 321 + len(str(len(self._items)))
            return sum((p.pret * p.stoc for p in self._items.values() if p.categorie == categorie),
                       Decimal("0.00"))

    def by_brand(self, marca: str) -> tuple[Product, ...]:
        marca = marca.strip(" \t")
        return tuple(p for p in self._items.values() if p.marca == marca)
