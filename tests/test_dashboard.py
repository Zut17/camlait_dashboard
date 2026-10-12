# camlait_dashboard/tests/test_dashboard.py
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCamlaitDashboard(TransactionCase):
    """Tests de regression de base pour camlait.dashboard.

    Objectif : proteger les methodes de calcul (get*) contre les
    regressions silencieuses (ex: le doublon de _get_target_warehouses /
    _get_target_location_ids qui existait auparavant en deux endroits du
    fichier, avec Python ne gardant que la derniere definition sans lever
    d'erreur). Ces tests ne verifient pas des valeurs metier precises
    (elles dependent des donnees presentes en base) mais que les methodes
    s'executent sans erreur et renvoient une structure coherente.
    """

    def setUp(self):
        super().setUp()
        self.dashboard = self.env['camlait.dashboard']

    def test_get_dashboard_data_keys(self):
        """get_dashboard_data() doit renvoyer toutes les sections attendues,
        sans lever d'exception, quelle que soit la volumetrie de donnees."""
        result = self.dashboard.get_dashboard_data()
        expected_keys = {
            'achats', 'ventes', 'stock', 'maintenance',
            'commandes_recentes', 'alertes', 'repartition_canal',
            'achats_categories', 'bons_commande_recents',
            'produits_sous_seuil_liste', 'stock_emplacements',
            'alertes_achats', 'alertes_stock', 'date_from', 'date_to',
        }
        self.assertTrue(expected_keys.issubset(result.keys()))

    def test_get_dashboard_data_with_explicit_dates(self):
        """Un appel avec des dates explicites doit etre repris tel quel
        dans la reponse (date_from / date_to echoes)."""
        result = self.dashboard.get_dashboard_data(
            date_from='2026-01-01', date_to='2026-01-31')
        self.assertEqual(result['date_from'], '2026-01-01')
        self.assertEqual(result['date_to'], '2026-01-31')

    def test_get_dashboard_data_cache(self):
        """Deux appels rapproches avec les memes parametres doivent
        renvoyer un resultat coherent (le cache court ne doit jamais
        renvoyer une structure invalide ou perimee au point de manquer
        des cles)."""
        first = self.dashboard.get_dashboard_data(date_from='2026-01-01', date_to='2026-01-31')
        second = self.dashboard.get_dashboard_data(date_from='2026-01-01', date_to='2026-01-31')
        self.assertEqual(first['date_from'], second['date_from'])
        self.assertEqual(first['date_to'], second['date_to'])

    def test_target_warehouses_no_duplicate_definition(self):
        """_get_target_warehouses / _get_target_location_ids ne doivent
        exister qu'une seule fois dans la classe (regression du bug des
        methodes dupliquees). On verifie indirectement que l'appel
        fonctionne et renvoie un recordset de stock.warehouse."""
        warehouses = self.dashboard._get_target_warehouses()
        self.assertEqual(warehouses._name, 'stock.warehouse')

        loc_ids = self.dashboard._get_target_location_ids()
        self.assertIsInstance(loc_ids, list)

    def test_stock_rotation_detail_default_period(self):
        """Sans argument, la periode de rotation doit rester 30 jours
        (comportement historique conserve pour compatibilite)."""
        result = self.dashboard.get_stock_rotation_detail()
        self.assertEqual(result['recap']['period_days'], 30)
        self.assertIn('rotation', result['recap'])
        self.assertIn('detail', result)

    def test_stock_rotation_detail_custom_period(self):
        """La fenetre de calcul de la rotation doit etre ajustable (ex: 7
        jours pour des produits a peremption rapide comme les produits
        laitiers), sans erreur meme sur une petite periode."""
        result = self.dashboard.get_stock_rotation_detail(period_days=7)
        self.assertEqual(result['recap']['period_days'], 7)

    def test_stock_rotation_detail_invalid_period_falls_back(self):
        """Une valeur invalide pour period_days ne doit pas faire planter
        l'appel : on retombe sur la valeur par defaut (30)."""
        result = self.dashboard.get_stock_rotation_detail(period_days='not-a-number')
        self.assertEqual(result['recap']['period_days'], 30)

    def test_get_stock_structure(self):
        """_get_stock() doit toujours renvoyer les cles utilisees par le
        front-end (le JS accede directement a ces champs sans garde)."""
        stock = self.dashboard._get_stock()
        for key in ('produits_en_stock', 'sous_seuil', 'ruptures',
                    'rotation_stock', 'taux_dispo', 'valeur_stock',
                    'produits_en_stock_qty', 'avarie_qty', 'echantillon_qty'):
            self.assertIn(key, stock)

    def test_get_bons_commande_recents_period_filter(self):
        """Regression : la carte 'Bons de commande recents' doit
        respecter la periode du dashboard (avant, elle ignorait
        completement dt_from/dt_to et affichait les 6 derniers BdC toutes
        dates confondues)."""
        today = date.today()
        dt_from = fields.Datetime.to_datetime(str(today.replace(day=1)))
        dt_to = fields.Datetime.to_datetime(str(today)).replace(hour=23, minute=59, second=59)
        result = self.dashboard._get_bons_commande_recents(dt_from, dt_to)
        self.assertIsInstance(result, list)
        # Sans periode (comportement historique), l'appel doit aussi
        # continuer a fonctionner (dt_from/dt_to optionnels).
        result_sans_periode = self.dashboard._get_bons_commande_recents()
        self.assertIsInstance(result_sans_periode, list)

    def test_facture_domain_values(self):
        """_facture_domain() ne doit jamais planter et ne doit ajouter
        AUCUNE contrainte pour 'tous' / None (doit inclure les commandes
        jamais facturees, comme demande), et une contrainte coherente pour
        'payee' / 'non_payee'."""
        self.assertEqual(self.dashboard._facture_domain('invoice_ids', None), [])
        self.assertEqual(self.dashboard._facture_domain('invoice_ids', 'tous'), [])
        payee = self.dashboard._facture_domain('invoice_ids', 'payee')
        self.assertEqual(payee, [('invoice_ids.payment_state', '=', 'paid')])
        non_payee = self.dashboard._facture_domain('invoice_ids', 'non_payee')
        self.assertEqual(non_payee[0][0], 'invoice_ids.payment_state')
        self.assertEqual(non_payee[0][1], 'in')

    def test_get_ventes_evolution_with_facture_filter(self):
        """Le graphique 'Evolution des ventes' doit accepter le nouveau
        parametre facture_ventes sans lever d'erreur, pour chacune des 3
        valeurs possibles."""
        for facture_filter in (None, 'payee', 'non_payee', 'tous'):
            result = self.dashboard.get_ventes_evolution(facture_ventes=facture_filter)
            self.assertIn('evolution', result)
            self.assertIsInstance(result['evolution'], list)

    def test_get_stock_no_target_locations_regression(self):
        """Regression du bug de production : "'>' not supported between
        instances of 'NoneType' and 'int'".

        Quand aucun emplacement cible n'est trouve (ou, en production,
        quand aucun stock.move 'done' vers un emplacement client ne tombe
        dans la fenetre des 30 derniers jours -- ce qui arrive des qu'une
        periode selectionnee n'a aucune sortie), le domaine de recherche
        des mouvements de sortie ne correspond a AUCUN enregistrement.
        read_group() renvoie alors un groupe dont la valeur agregee
        'product_qty' vaut None (et non 0.0). Avant correction,
        'sorties_30j / 30 if sorties_30j > 0 else 0' comparait directement
        None a 0 et levait TypeError, faisant planter tout
        get_dashboard_data() (et afficher le message d'erreur generique
        du tableau de bord).

        On force ce cas ici en simulant l'absence d'emplacements cibles,
        independamment des donnees de demo presentes en base (qui
        pourraient ou non contenir des mouvements recents)."""
        with patch.object(
            type(self.dashboard), '_get_target_location_ids', return_value=[],
        ):
            stock = self.dashboard._get_stock()
        self.assertEqual(stock['rotation_stock'], 0)
        self.assertEqual(stock['produits_en_stock'], 0)
        self.assertEqual(stock['ruptures'], 0)
        self.assertEqual(stock['valeur_stock'], 0.0)

    def test_get_dashboard_data_cache_key_includes_dbname(self):
        """Regression : sur un serveur Odoo heberge en multi-bases
        (plusieurs clients sur le meme worker), la cle du cache court de
        get_dashboard_data() doit inclure le nom de la base
        (self.env.cr.dbname), sinon un meme couple (company_id, uid)
        present dans deux bases differentes pourrait faire fuiter le
        resultat calcule pour une base vers une autre. On verifie que la
        cle utilisee dans le cache module-level commence bien par le nom
        de la base courante."""
        from odoo.addons.camlait_dashboard.models.dashboard import _DASHBOARD_CACHE

        self.dashboard.get_dashboard_data(date_from='2026-01-01', date_to='2026-01-31')
        matching_keys = [k for k in _DASHBOARD_CACHE if k[0] == self.env.cr.dbname]
        self.assertTrue(matching_keys, "La cle de cache devrait commencer par le nom de la base")
