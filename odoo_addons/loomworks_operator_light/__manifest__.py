{
    "name": "Loomworks Operator Light",
    "summary": "Simplified operator canvas workflow embedded directly in Odoo.",
    "description": (
        "Provides a lightweight alternative to the external Loomworks Operator "
        "wrapper by storing prompts and generating placeholder layouts inside "
        "Odoo. Useful for rehearsing workflows before the full AI backend is ready."
    ),
    "version": "0.1.0",
    "author": "Loomworks",
    "website": "https://loomworks.ai",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/operator_session_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
