import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from magazin.inventory import Inventory, Product
finally:
    sys.path.pop(0)


HEADER = "cod;pret;marca;an;garantie;producator;tara;categorie;stoc"
ROW = "X;0.10;Acme;1980;0;Factory;RO;CPU;3"
ITEM = Product("X", Decimal("0.10"), "Acme", 1980, 0, "Factory", "RO", "CPU", 3)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "inventory.csv"
        self.inv = Inventory()

    def test_no_mutations_before_choosing_path(self):
        for fn, args in ((self.inv.add, (ITEM,)), (self.inv.sell, ("X",)),
                         (self.inv.restock, ("X", 1)), (self.inv.delete, ("X",))):
            with self.subTest(fn=fn.__name__), self.assertRaises(ValueError):
                fn(*args)
        self.assertIsNone(self.inv.path)
        self.assertEqual(self.inv.products, ())

    def test_optional_headers_and_export(self):
        for header in ("", HEADER + "\n", "  CoD_PrOdUs ;other labels\n"):
            with self.subTest(header=header):
                self.path.write_text("\n" + header + "  " + ROW + " \t\n", encoding="utf-8-sig")
                self.assertEqual(self.inv.load(self.path), [])
                self.assertEqual(self.inv.products, (ITEM,))
                dest = self.path.with_suffix(".copy")
                self.inv.save_as(dest)
                self.assertEqual(self.inv.path, dest)
                self.assertEqual(dest.read_text(encoding="utf-8"), HEADER + "\n" + ROW + "\n")

    def test_warnings_keep_first_valid_code_and_continue(self):
        rows = [HEADER, "", "bad", ROW, ROW.replace("0.10", "42"),
                ROW.replace("1980", "2027"), ROW.replace("0.10", "NaN"),
                ROW + ";extra", ROW.replace("0.10", "1_000"), ROW.replace("1980", "1980abc"),
                ROW.replace("Factory", ""), ROW.replace("X;", "x;")]
        self.path.write_bytes("\r\n".join(rows).encode() + b"\r\n\xff\n")
        warnings = self.inv.load(self.path)
        self.assertEqual([w.split(":")[0] for w in warnings],
                         [f"Linia {n}" for n in (3, 5, 6, 7, 8, 9, 10, 11, 13)])
        self.assertIn("duplicat X", warnings[1])
        self.assertEqual(self.inv.products, (ITEM, replace(ITEM, cod="x")))

    def test_product_validation(self):
        for field in ("cod", "marca", "producator", "tara", "categorie"):
            for value in ("  ", "a;b", "\nb", "c\r"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(ITEM, **{field: value})
        for field, value in (("an", 1979), ("an", 2027), ("stoc", -1), ("garantie", -1),
                             ("stoc", True), ("pret", Decimal("Infinity")), ("pret", Decimal("-0.001"))):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(ITEM, **{field: value})

    def test_sales_restock_delete_and_reports_round_trip(self):
        other = replace(ITEM, cod="Y", an=2026, categorie="RAM", pret=Decimal("2.3456"))
        third = replace(ITEM, cod="Z", marca="acme", pret=Decimal("0.20"))
        self.inv.save_as(self.path)
        for item in (ITEM, other, third):
            self.inv.add(item)
        snapshot = self.inv.products
        self.inv.sell("X")
        self.inv.restock("Z", 2)
        self.assertEqual(self.inv.total("CPU"), Decimal("1.20"))
        self.assertEqual(self.inv.total("RAM"), Decimal("7.05"))
        self.assertEqual(self.inv.total("cpu"), Decimal(0))
        self.assertEqual([p.cod for p in self.inv.by_brand("Acme")], ["X", "Y"])
        self.assertEqual(snapshot[0].stoc, 3)
        with self.assertRaises(FrozenInstanceError):
            snapshot[0].stoc = 0
        self.inv.delete("Y")
        reopened = Inventory()
        self.assertEqual(reopened.load(self.path), [])
        self.assertEqual(reopened.products, (replace(ITEM, stoc=2), replace(third, stoc=5)))

    def test_rejected_transactions(self):
        self.inv.save_as(self.path)
        empty = replace(ITEM, stoc=0)
        self.inv.add(empty)
        original = self.path.read_bytes()
        for fn, args in ((self.inv.add, (ITEM,)), (self.inv.sell, ("X",)), (self.inv.sell, ("x",)),
                         (self.inv.restock, ("Y", 1)), (self.inv.restock, ("X", 0)),
                         (self.inv.restock, ("X", True)), (self.inv.delete, ("Y",))):
            with self.subTest(fn=fn.__name__, args=args), self.assertRaises(ValueError):
                fn(*args)
        self.assertEqual(self.inv.products, (empty,))
        self.assertEqual(self.path.read_bytes(), original)

    def test_persistence_failure_rolls_back(self):
        self.inv.save_as(self.path)
        self.inv.add(ITEM)
        original = self.path.read_bytes()
        other = self.path.with_suffix(".other")
        other.write_bytes(b"existing destination")
        with patch("magazin.inventory.os.replace", side_effect=PermissionError("locked")):
            for fn, args in ((self.inv.add, (replace(ITEM, cod="Y"),)), (self.inv.sell, ("X",)),
                             (self.inv.restock, ("X", 1)), (self.inv.delete, ("X",)),
                             (self.inv.save_as, (other,))):
                with self.subTest(fn=fn.__name__):
                    with self.assertRaises(OSError):
                        fn(*args)
                    self.assertEqual(self.inv.path, self.path)
                    self.assertEqual(self.inv.products, (ITEM,))
                    self.assertEqual(self.path.read_bytes(), original)
                    self.assertEqual(other.read_bytes(), b"existing destination")
                    self.assertEqual(set(self.path.parent.iterdir()), {self.path, other})

    def test_failed_load_preserves_active_inventory(self):
        self.inv.save_as(self.path)
        self.inv.add(ITEM)
        with self.assertRaises(OSError):
            self.inv.load(self.path.with_suffix(".missing"))
        self.assertEqual(self.inv.path, self.path)
        self.assertEqual(self.inv.products, (ITEM,))
