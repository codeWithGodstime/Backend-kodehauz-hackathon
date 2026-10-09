"""Application package.

Python 3.14 stores class annotations on ``__annotate_func__``. sqlmodel 0.0.22
only reads ``__annotations__``, so every SQLModel class fails to build.
Patch the lookup before the rest of the app imports models.
"""

import sys

if sys.version_info >= (3, 14):
    import annotationlib
    import sqlmodel.main as _sqlmodel_main

    def _annotations_from_class_dict(class_dict: dict) -> dict:
        annotations = class_dict.get("__annotations__") or {}
        if annotations:
            return annotations
        annotate = class_dict.get("__annotate_func__") or class_dict.get("__annotate__")
        if annotate is None:
            return {}
        return annotationlib.call_annotate_function(
            annotate, format=annotationlib.Format.VALUE
        )

    _sqlmodel_main.get_annotations = _annotations_from_class_dict
