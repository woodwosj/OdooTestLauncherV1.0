from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from odoo import _, fields, models


class OperatorSession(models.Model):
    _name = "loomworks.operator.session"
    _description = "Loomworks Operator Session"
    _order = "create_date desc"

    name = fields.Char(
        string="Session Name",
        required=True,
        default=lambda self: _("New Session"),
        help="Friendly label used in the menu and search views.",
    )
    prompt = fields.Text(
        string="Prompt",
        required=True,
        help="Business question or instruction that the operator should address.",
    )
    response = fields.Text(
        string="Response Summary",
        readonly=True,
        help="Human-readable summary produced by the lightweight layout generator.",
    )
    layout_json = fields.Text(
        string="Layout JSON",
        readonly=True,
        help="Declarative layout emitted by the simplified generator (for review or export).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    last_run_at = fields.Datetime(
        string="Last Generated",
        readonly=True,
    )

    def write(self, vals: dict[str, Any]) -> bool:
        if vals.get("state") == "draft":
            vals.setdefault("response", False)
            vals.setdefault("layout_json", False)
            vals.setdefault("last_run_at", False)
        return super().write(vals)

    def action_generate_layout(self) -> None:
        template = _(
            "Prompt: %(prompt)s\n"
            "Session generated on %(date)s.\n"
            "Use the Layout JSON field to preview or hand off a canvas definition."
        )
        now_iso = fields.Datetime.now()
        for record in self:
            layout = record._build_placeholder_layout()
            record.write(
                {
                    "response": template
                    % {
                        "prompt": record.prompt or _("(no prompt provided)"),
                        "date": fields.Datetime.to_string(now_iso),
                    },
                    "layout_json": json.dumps(layout, indent=2),
                    "state": "generated",
                    "last_run_at": now_iso,
                }
            )

    def action_set_draft(self) -> None:
        for record in self:
            record.write(
                {
                    "state": "draft",
                    "response": False,
                    "layout_json": False,
                    "last_run_at": False,
                }
            )

    def action_archive(self) -> None:
        for record in self:
            record.write({"state": "archived"})

    def _build_placeholder_layout(self) -> dict[str, Any]:
        recency = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "layout_type": "dashboard",
            "generated_at": recency,
            "cards": [
                {
                    "title": _("Outstanding Actions"),
                    "value": 3,
                    "hint": _("Follow up on quotations and late invoices."),
                },
                {
                    "title": _("Next Steps"),
                    "value": _("Review warehouse transfers for accuracy."),
                },
            ],
            "table": {
                "title": _("Suggested Records"),
                "model": "sale.order",
                "columns": ["name", "partner_id", "amount_total", "state"],
                "domain": "[('state', 'in', ['sent', 'sale'])]",
            },
            "notes": _(
                "This layout is generated locally for rehearsal and does not call the external AI services."
            ),
        }
