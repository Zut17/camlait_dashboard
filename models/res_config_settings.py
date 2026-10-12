# camlait_dashboard/models/res_config_settings.py
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    """Expose 'budget_achats' / 'objectif_ca' dans Reglages > Parametres
    generaux, en plus de l'icone de reglages dediee du tableau de bord.

    Les deux champs pointent (via config_parameter) sur les MEMES cles
    ir.config_parameter ('camlait_dashboard.budget_achats' /
    'camlait_dashboard.objectif_ca') que celles lues/ecrites par
    camlait.dashboard.get_settings() / save_settings() : une seule source
    de verite, juste deux endroits pour la modifier (icone du dashboard
    pour un usage courant, Reglages pour un usage plus "administrateur
    Odoo classique").
    """
    _inherit = 'res.config.settings'

    camlait_budget_achats = fields.Float(
        string='Budget achats mensuel',
        config_parameter='camlait_dashboard.budget_achats',
        default=95_800_000.0,
        help="Objectif de budget achats utilisé par la carte 'Budget "
            "achats consommé' du tableau de bord Camlait.",
    )
    camlait_objectif_ca = fields.Float(
        string="Objectif de chiffre d'affaires mensuel",
        config_parameter='camlait_dashboard.objectif_ca',
        default=197_000_000.0,
        help="Objectif de CA utilisé par la carte 'Chiffre d'affaires' du "
            "tableau de bord Camlait.",
    )
