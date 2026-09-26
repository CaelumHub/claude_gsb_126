import asyncio
import os
import tempfile
import unittest


os.environ.setdefault("WB_DATA_DIR", tempfile.mkdtemp(prefix="coboard-tests-"))

from backend.boards import manager
from backend.crdt import BoardDoc, sanitize_shape
from backend.export import render_mindmap_links
from backend.templates import build_template_shapes


class MindmapReferenceTests(unittest.TestCase):
    def test_sanitize_shape_preserves_parent_for_add_and_snapshot(self):
        root = sanitize_shape({
            "id": "root", "kind": "mindnode", "x": 0, "y": 0,
            "w": 100, "h": 40, "parent": None,
        })
        child = sanitize_shape({
            "id": "child", "kind": "mindnode", "x": 120, "y": 0,
            "w": 100, "h": 40, "parent": "root",
        })

        self.assertIsNone(root["parent"])
        self.assertEqual(child["parent"], "root")

        doc = BoardDoc("snapshot-roundtrip")
        doc.import_state({"shapes": {"child": child}})
        self.assertEqual(doc.shapes["child"]["parent"], "root")

    def test_template_instantiation_remaps_parent_references(self):
        shapes = build_template_shapes("project-plan", mode="mindmap")
        by_old_parent = {
            shape["id"]: shape.get("parent")
            for shape in shapes
            if shape.get("kind") == "mindnode" and shape.get("parent")
        }

        self.assertGreater(len(by_old_parent), 1)
        ids = {shape["id"] for shape in shapes}
        self.assertTrue(by_old_parent)
        self.assertTrue(all(parent in ids for parent in by_old_parent.values()))

    def test_board_duplication_remaps_parent_references(self):
        async def scenario():
            source_meta = await manager.create_board("源思维导图", "mindmap", "tester")
            source_id = source_meta["id"]
            source = await manager.get_doc(source_id)

            root = {
                "id": "source-root", "kind": "mindnode", "x": 0, "y": 0,
                "w": 100, "h": 40, "parent": None,
            }
            child = {
                "id": "source-child", "kind": "mindnode", "x": 120, "y": 0,
                "w": 100, "h": 40, "parent": "source-root",
            }
            source.shapes.clear()
            source.apply_op({
                "op_id": "test:1", "site": "test", "lam": 1, "ts": 1,
                "type": "add_shape", "base_rev": 0, "shape": root,
            })
            source.apply_op({
                "op_id": "test:2", "site": "test", "lam": 2, "ts": 2,
                "type": "add_shape", "base_rev": 0, "shape": child,
            })

            copy_meta = await manager.duplicate_board(source_id, "副本思维导图", "tester")
            copy = await manager.get_doc(copy_meta["id"])
            copies = [s for s in copy.visible_shapes() if s["kind"] == "mindnode"]
            by_id = {s["id"]: s for s in copies}
            copied_child = next(s for s in copies if s.get("parent"))
            copied_root = by_id[copied_child["parent"]]

            self.assertEqual(len(copies), 2)
            self.assertIsNone(copied_root.get("parent"))
            self.assertNotEqual(copied_child["parent"], "source-root")
            self.assertIn(copied_child["parent"], by_id)

        asyncio.run(scenario())

    def test_svg_export_reads_parent_reference(self):
        root = {"id": "root", "kind": "mindnode", "x": 0, "y": 0, "w": 100, "h": 40}
        child = {"id": "child", "kind": "mindnode", "x": 120, "y": 10,
                 "w": 100, "h": 40, "parent": "root"}

        svg = render_mindmap_links([root, child])

        self.assertIn('M 100.0 20.0', svg)
        self.assertIn('C 110.0 20.0 110.0 30.0 120.0 30.0', svg)


if __name__ == "__main__":
    unittest.main()
