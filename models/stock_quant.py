# camlait_dashboard/models/stock_quant.py
from odoo import models, fields, api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    camlait_currency_id = fields.Many2one(
        'res.currency', string='Devise',
        related='company_id.currency_id', readonly=True,
    )
    camlait_standard_price = fields.Float(
        related='product_id.standard_price',
        string='Prix de revient',
        store=True
    )
    camlait_valeur_stock = fields.Float(
        string='Valeur du stock',
        compute='_compute_camlait_valeur_stock', store=True,
        help="Quantité x Coût standard du produit. Sert à mettre en évidence "
            "la valorisation du stock (mêmes valeurs que la carte "
            "'Valeur stock actuel' du tableau de bord Camlait).",
    )
    camlait_product_type = fields.Selection(
        related='product_id.type', string='Type de produit',
        store=True, index=True,
        help="Related stocke + indexe sur product_id.type ('product' = "
            "stockable, 'consu' = consommable, 'service' = service). Le "
            "tableau de bord Camlait filtre tres frequemment les quants "
            "par ('product_id.type', '=', 'product') : sans ce champ, "
            "chaque recherche force une jointure/sous-requete implicite "
            "vers product.product puis product.template. Avec ce champ "
            "stocke et indexe sur stock.quant, le meme filtre devient un "
            "simple WHERE sur colonne indexee -- nettement plus rapide "
            "des que le volume de quants grossit.",
    )

    @api.depends('quantity', 'camlait_standard_price')
    def _compute_camlait_valeur_stock(self):
        for quant in self:
            quant.camlait_valeur_stock = quant.quantity * quant.camlait_standard_price
