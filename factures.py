"""
SODIPAC - Génération de factures / reçus imprimables (HTML → navigateur → impression)
"""

import os
import tempfile
import webbrowser
from datetime import datetime

import database as db


def _echapper(texte: str) -> str:
    return (str(texte or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _money(v, devise: str) -> str:
    return f"{float(v or 0):,.0f}".replace(",", " ") + f" {devise}"


def generer_facture_html(vente_id: int, format_ticket: bool = False) -> tuple[str | None, str | None]:
    """Construit le HTML de la facture. format_ticket=True → rouleau 80mm."""
    vente, lignes = db.get_vente_details(vente_id)
    if not vente:
        return None, "Vente introuvable"

    p = db.get_parametres()
    devise = p.get("devise", "F CFA")
    largeur = "80mm" if format_ticket else "210mm"
    taille_police = "11px" if format_ticket else "13px"

    client = None
    if vente.get("client_id"):
        client = next((c for c in db.get_clients() if c["id"] == vente["client_id"]), None)

    lignes_html = []
    for i, l in enumerate(lignes, 1):
        lignes_html.append(f"""
        <tr>
          <td class="c">{i}</td>
          <td>{_echapper(l['reference'])}</td>
          <td>{_echapper(l['produit_nom'])}</td>
          <td class="c">{l['quantite']}</td>
          <td class="r">{_money(l['prix_unitaire'], '')}</td>
          <td class="r"><b>{_money(l['total'], '')}</b></td>
        </tr>""")

    remise = float(vente.get("remise") or 0)
    sous_total = float(vente.get("sous_total") or vente["total"])
    total = float(vente["total"])
    paye = float(vente.get("montant_paye") or total)
    rendu = max(0.0, paye - total)

    bloc_remise = ""
    if remise > 0:
        bloc_remise = f"""<tr><td>Remise</td><td class="r">- {_money(remise, devise)}</td></tr>"""

    bloc_rendu = ""
    if rendu > 0:
        bloc_rendu = (f"""<tr><td>Montant reçu</td><td class="r">{_money(paye, devise)}</td></tr>"""
                      f"""<tr><td>Monnaie rendue</td><td class="r">{_money(rendu, devise)}</td></tr>""")

    annulee = (vente.get("statut") == "annulee")
    filigrane = ('<div class="annule">VENTE ANNULÉE</div>' if annulee else "")

    infos_client = f"""
      <div class="bloc">
        <div class="lbl">CLIENT</div>
        <div><b>{_echapper(vente['client_nom'])}</b></div>
        {f"<div>Tél : {_echapper(client['telephone'])}</div>" if client and client.get('telephone') else ""}
        {f"<div>Véhicule : {_echapper(client['vehicule'])}</div>" if client and client.get('vehicule') else ""}
      </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>{_echapper(vente.get('numero') or vente_id)}</title>
<style>
  @page {{ size: {'80mm auto' if format_ticket else 'A4'}; margin: {'4mm' if format_ticket else '14mm'}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {taille_police};
          color: #1f2933; margin: 0 auto; max-width: {largeur}; padding: 8px;
          background: #fff; position: relative; }}
  .entete {{ display: flex; justify-content: space-between; align-items: flex-start;
             border-bottom: 3px solid #1a73e8; padding-bottom: 10px; margin-bottom: 14px; }}
  .logo {{ font-size: 22px; font-weight: 700; color: #1a73e8; letter-spacing: 1px; }}
  .soc {{ color: #6b7785; font-size: 11px; line-height: 1.5; }}
  .titre {{ text-align: right; }}
  .titre h1 {{ margin: 0; font-size: 20px; color: #1f2933; }}
  .num {{ font-family: monospace; font-size: 13px; color: #1a73e8; font-weight: 700; }}
  .infos {{ display: flex; gap: 16px; margin-bottom: 14px; }}
  .bloc {{ flex: 1; background: #f7f9fc; border: 1px solid #d6dce5;
           border-radius: 4px; padding: 8px 10px; font-size: 11px; line-height: 1.6; }}
  .lbl {{ font-size: 9px; letter-spacing: 1px; color: #6b7785; margin-bottom: 3px; }}
  table.art {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
  table.art th {{ background: #1c2833; color: #fff; padding: 7px 6px; font-size: 10px;
                  text-align: left; letter-spacing: .5px; }}
  table.art td {{ padding: 6px; border-bottom: 1px solid #e6ebf2; }}
  table.art tr:nth-child(even) td {{ background: #f7f9fc; }}
  .c {{ text-align: center; }} .r {{ text-align: right; }}
  .totaux {{ margin-left: auto; width: {'100%' if format_ticket else '55%'}; }}
  .totaux table {{ width: 100%; border-collapse: collapse; }}
  .totaux td {{ padding: 5px 8px; border-bottom: 1px solid #e6ebf2; }}
  .totaux tr.grand td {{ background: #1a73e8; color: #fff; font-size: 15px;
                         font-weight: 700; border: 0; }}
  .pied {{ margin-top: 20px; padding-top: 10px; border-top: 1px dashed #d6dce5;
           text-align: center; color: #6b7785; font-size: 10px; line-height: 1.6; }}
  .annule {{ position: fixed; top: 42%; left: 50%; transform: translate(-50%,-50%) rotate(-24deg);
             font-size: 60px; font-weight: 800; color: rgba(198,40,40,.18);
             border: 6px solid rgba(198,40,40,.18); padding: 10px 30px; pointer-events: none; }}
  .barre {{ text-align:center; margin: 14px 0; }}
  .barre button {{ background:#1a73e8; color:#fff; border:0; padding:10px 22px;
                   font-size:14px; border-radius:5px; cursor:pointer; font-family: inherit; }}
  @media print {{ .barre {{ display: none; }} body {{ padding: 0; }} }}
</style></head>
<body>
{filigrane}
<div class="entete">
  <div>
    <div class="logo">🚗 {_echapper(p.get('entreprise_nom', 'SODIPAC'))}</div>
    <div class="soc">
      {_echapper(p.get('entreprise_activite', ''))}<br>
      {_echapper(p.get('entreprise_adresse', ''))}<br>
      {('Tél : ' + _echapper(p.get('entreprise_telephone'))) if p.get('entreprise_telephone') else ''}
      {(' • ' + _echapper(p.get('entreprise_email'))) if p.get('entreprise_email') else ''}
    </div>
  </div>
  <div class="titre">
    <h1>{'REÇU' if format_ticket else 'FACTURE'}</h1>
    <div class="num">{_echapper(vente.get('numero') or f'#{vente_id}')}</div>
  </div>
</div>

<div class="infos">
  <div class="bloc">
    <div class="lbl">DÉTAILS</div>
    <div>Date : <b>{_echapper(str(vente['date_vente'])[:16])}</b></div>
    <div>Paiement : <b>{_echapper(vente.get('mode_paiement') or 'Espèces')}</b></div>
    <div>Vendeur : {_echapper(vente.get('utilisateur') or '-')}</div>
  </div>
  {infos_client}
</div>

<table class="art">
  <thead><tr>
    <th class="c">#</th><th>RÉFÉRENCE</th><th>DÉSIGNATION</th>
    <th class="c">QTÉ</th><th class="r">P.U.</th><th class="r">TOTAL</th>
  </tr></thead>
  <tbody>{''.join(lignes_html)}</tbody>
</table>

<div class="totaux"><table>
  <tr><td>Sous-total</td><td class="r">{_money(sous_total, devise)}</td></tr>
  {bloc_remise}
  <tr class="grand"><td>NET À PAYER</td><td class="r">{_money(total, devise)}</td></tr>
  {bloc_rendu}
</table></div>

<div class="barre"><button onclick="window.print()">🖨️ Imprimer</button></div>

<div class="pied">
  {_echapper(p.get('pied_facture', 'Merci de votre confiance !'))}<br>
  Document généré le {datetime.now():%d/%m/%Y à %H:%M} par {_echapper(p.get('entreprise_nom', 'SODIPAC'))}
</div>
</body></html>"""
    return html, None


def imprimer_facture(vente_id: int, format_ticket: bool = False, ouvrir: bool = True) -> tuple[bool, str]:
    """Génère la facture et l'ouvre dans le navigateur (dialogue d'impression natif)."""
    html, erreur = generer_facture_html(vente_id, format_ticket)
    if erreur:
        return False, erreur

    dossier = os.path.join(db.BASE_DIR, "factures")
    os.makedirs(dossier, exist_ok=True)
    vente, _ = db.get_vente_details(vente_id)
    nom = f"{(vente.get('numero') or vente_id)}{'_ticket' if format_ticket else ''}.html"
    # Nettoyage des caractères interdits sous Windows dans un nom de fichier
    for c in '\\/:*?"<>|':
        nom = nom.replace(c, "-")
    chemin = os.path.join(dossier, nom)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(html)
    if ouvrir:
        webbrowser.open(f"file:///{chemin.replace(os.sep, '/')}")
    return True, chemin


def generer_rapport_html(titre: str, date_debut: str, date_fin: str, donnees: list | dict, ouvrir: bool = True) -> str:
    """Rapport de ventes imprimable."""
    p = db.get_parametres()
    devise = p.get("devise", "F CFA")
    r = donnees["resume"]

    def tableau(entetes: list | dict, lignes: list | dict, aligne_droite=()):
        th = "".join(f"<th class='{'r' if i in aligne_droite else ''}'>{_echapper(h)}</th>"
                     for i, h in enumerate(entetes))
        trs = []
        for ligne in lignes:
            tds = "".join(f"<td class='{'r' if i in aligne_droite else ''}'>{_echapper(c)}</td>"
                          for i, c in enumerate(ligne))
            trs.append(f"<tr>{tds}</tr>")
        if not trs:
            trs.append(f"<tr><td colspan='{len(entetes)}' style='text-align:center;color:#6b7785'>"
                       "Aucune donnée sur la période</td></tr>")
        return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"

    marge_pct = (r["marge"] / r["ca"] * 100) if r["ca"] else 0

    cartes = [
        ("Chiffre d'affaires", _money(r["ca"], devise), "#1a73e8"),
        ("Marge brute", _money(r["marge"], devise), "#2e7d32"),
        ("Taux de marge", f"{marge_pct:.1f} %", "#0277bd"),
        ("Ventes", f"{r['nb_ventes']}", "#546e7a"),
        ("Panier moyen", _money(r["panier_moyen"], devise), "#ef6c00"),
        ("Articles vendus", f"{r['articles_vendus']}", "#546e7a"),
    ]
    cartes_html = "".join(
        f"""<div class="kpi"><div class="k">{_echapper(t)}</div>
            <div class="v" style="color:{c}">{_echapper(v)}</div></div>"""
        for t, v, c in cartes)

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{_echapper(titre)}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; font-size:12px; color:#1f2933;
          max-width:900px; margin:0 auto; padding:14px; }}
  h1 {{ color:#1a73e8; margin:0 0 2px; font-size:22px; }}
  h2 {{ font-size:14px; margin:22px 0 8px; padding-bottom:5px;
        border-bottom:2px solid #1a73e8; color:#1c2833; }}
  .sous {{ color:#6b7785; margin-bottom:16px; font-size:11px; }}
  .kpis {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:8px; }}
  .kpi {{ flex:1 1 140px; background:#f7f9fc; border:1px solid #d6dce5;
          border-radius:5px; padding:10px 12px; }}
  .kpi .k {{ font-size:9px; letter-spacing:.8px; color:#6b7785; text-transform:uppercase; }}
  .kpi .v {{ font-size:18px; font-weight:700; margin-top:3px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:10px; }}
  th {{ background:#1c2833; color:#fff; padding:7px 6px; text-align:left; font-size:10px; }}
  td {{ padding:6px; border-bottom:1px solid #e6ebf2; }}
  tr:nth-child(even) td {{ background:#f7f9fc; }}
  .r {{ text-align:right; }}
  .barre {{ text-align:center; margin:16px 0; }}
  .barre button {{ background:#1a73e8;color:#fff;border:0;padding:10px 22px;
                   border-radius:5px;cursor:pointer;font-size:14px;font-family:inherit; }}
  .pied {{ margin-top:24px; text-align:center; color:#6b7785; font-size:10px;
           border-top:1px dashed #d6dce5; padding-top:10px; }}
  @media print {{ .barre {{ display:none; }} }}
</style></head><body>
<h1>{_echapper(p.get('entreprise_nom', 'SODIPAC'))} — {_echapper(titre)}</h1>
<div class="sous">Période du {_echapper(date_debut)} au {_echapper(date_fin)}
  • édité le {datetime.now():%d/%m/%Y %H:%M}</div>

<div class="kpis">{cartes_html}</div>

<h2>Ventes par jour</h2>
{tableau(["Date", "Nombre de ventes", "Chiffre d'affaires"],
         [[d["jour"], d["nb"], _money(d["ca"], devise)] for d in donnees["par_jour"]], (1, 2))}

<h2>Ventes par catégorie</h2>
{tableau(["Catégorie", "Quantité", "Chiffre d'affaires"],
         [[d["categorie"], d["qte"], _money(d["ca"], devise)] for d in donnees["par_categorie"]], (1, 2))}

<h2>Modes de paiement</h2>
{tableau(["Mode", "Nombre", "Montant"],
         [[d["mode"], d["nb"], _money(d["ca"], devise)] for d in donnees["par_paiement"]], (1, 2))}

<h2>Détail par produit</h2>
{tableau(["Référence", "Produit", "Qté vendue", "Chiffre d'affaires", "Marge"],
         [[d["reference"], d["nom"], d["qte"], _money(d["ca"], devise), _money(d["marge"], devise)]
          for d in donnees["par_produit"]], (2, 3, 4))}

<div class="barre"><button onclick="window.print()">🖨️ Imprimer / Enregistrer en PDF</button></div>
<div class="pied">{_echapper(p.get('entreprise_nom', 'SODIPAC'))} — rapport généré automatiquement</div>
</body></html>"""

    dossier = os.path.join(db.BASE_DIR, "rapports")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f"rapport_{date_debut}_{date_fin}.html")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(html)
    if ouvrir:
        webbrowser.open(f"file:///{chemin.replace(os.sep, '/')}")
    return chemin


def generer_liste_reappro(ouvrir: bool = True) -> str:
    """Bon de commande fournisseur basé sur les alertes de stock."""
    p = db.get_parametres()
    devise = p.get("devise", "F CFA")
    produits = db.get_produits(seulement_alertes=True, inclure_inactifs=False)

    par_fournisseur = {}
    for pr in produits:
        par_fournisseur.setdefault(pr["fournisseur_nom"] or "Fournisseur non défini", []).append(pr)

    sections = []
    total_general = 0
    for fournisseur, items in sorted(par_fournisseur.items()):
        lignes, sous_total = [], 0
        for pr in items:
            a_commander = max(pr["stock_mini"] * 2 - pr["stock"], 1)
            montant = a_commander * pr["prix_achat"]
            sous_total += montant
            lignes.append(f"""<tr>
              <td>{_echapper(pr['reference'])}</td>
              <td>{_echapper(pr['nom'])}</td>
              <td>{_echapper(pr['marque'])}</td>
              <td class="c">{pr['stock']}</td>
              <td class="c">{pr['stock_mini']}</td>
              <td class="c"><b>{a_commander}</b></td>
              <td class="r">{_money(pr['prix_achat'], '')}</td>
              <td class="r">{_money(montant, '')}</td></tr>""")
        total_general += sous_total
        sections.append(f"""
        <h2>{_echapper(fournisseur)}</h2>
        <table><thead><tr><th>Réf.</th><th>Produit</th><th>Marque</th>
          <th class="c">Stock</th><th class="c">Mini</th><th class="c">À commander</th>
          <th class="r">P.A.</th><th class="r">Montant</th></tr></thead>
        <tbody>{''.join(lignes)}</tbody>
        <tfoot><tr><td colspan="7" class="r"><b>Sous-total</b></td>
          <td class="r"><b>{_money(sous_total, devise)}</b></td></tr></tfoot></table>""")

    if not sections:
        sections.append("<p style='text-align:center;color:#2e7d32;padding:30px'>"
                        "✅ Aucun réapprovisionnement nécessaire : tous les stocks sont suffisants.</p>")

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Bon de réapprovisionnement</title><style>
  @page {{ size:A4; margin:12mm; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; font-size:12px; color:#1f2933;
          max-width:900px; margin:0 auto; padding:14px; }}
  h1 {{ color:#1a73e8; font-size:22px; margin:0 0 2px; }}
  h2 {{ font-size:14px; margin:20px 0 6px; color:#1c2833;
        border-bottom:2px solid #ef6c00; padding-bottom:4px; }}
  .sous {{ color:#6b7785; font-size:11px; margin-bottom:14px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:6px; }}
  th {{ background:#1c2833; color:#fff; padding:6px; text-align:left; font-size:10px; }}
  td {{ padding:6px; border-bottom:1px solid #e6ebf2; }}
  tr:nth-child(even) td {{ background:#f7f9fc; }}
  tfoot td {{ background:#fff4e6 !important; }}
  .c {{ text-align:center; }} .r {{ text-align:right; }}
  .total {{ background:#1a73e8; color:#fff; padding:12px; font-size:16px;
            font-weight:700; text-align:right; border-radius:5px; margin-top:12px; }}
  .barre {{ text-align:center; margin:16px 0; }}
  .barre button {{ background:#1a73e8;color:#fff;border:0;padding:10px 22px;
                   border-radius:5px;cursor:pointer;font-size:14px;font-family:inherit; }}
  @media print {{ .barre {{ display:none; }} }}
</style></head><body>
<h1>🚗 {_echapper(p.get('entreprise_nom', 'SODIPAC'))} — Bon de réapprovisionnement</h1>
<div class="sous">{len(produits)} produit(s) sous le seuil d'alerte
  • édité le {datetime.now():%d/%m/%Y %H:%M}</div>
{''.join(sections)}
{f'<div class="total">TOTAL ESTIMÉ : {_money(total_general, devise)}</div>' if produits else ''}
<div class="barre"><button onclick="window.print()">🖨️ Imprimer</button></div>
</body></html>"""

    dossier = os.path.join(db.BASE_DIR, "rapports")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f"reappro_{datetime.now():%Y%m%d_%H%M}.html")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(html)
    if ouvrir:
        webbrowser.open(f"file:///{chemin.replace(os.sep, '/')}")
    return chemin
