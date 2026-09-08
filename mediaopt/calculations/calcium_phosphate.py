"""calcium_phosphate precipitation risk - NOT YET PORTED.

The workbook's saturation-index model (activity coefficients by the Davies equation,
pH-dependent speciation, tabulated solubility products) is Phase 6. This module raises
rather than returning an approximation, because a wrong precipitation risk is worse
than none: the caller cannot tell a rough answer from a real one.

Reference implementation: the 'calcium_phosphate' worksheet of the workbook.
"""


def saturation_index(*args, **kwargs):
    raise NotImplementedError(
        "calcium_phosphate saturation index is not yet ported from the workbook (Phase 6). "
        "Use the workbook's own worksheet until it is."
    )
