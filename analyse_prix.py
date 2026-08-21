"""
SOPAUTO — Analyse des prix pratiqués et des tendances de vente
==============================================================

Dans une boutique de pièces auto, le prix affiché n'est qu'un point de
départ : le client négocie. Ce module mesure **l'écart réel entre le prix
catalogue et le prix effectivement pratiqué**, et détecte les produits dont
les ventes accélèrent ou s'effondrent.

Deux familles de fonctions :

  A. PRIX PRATIQUÉS (remise / majoration)
     • analyse_prix_pratiques()   → par produit : tendance à brader ou majorer
     • synthese_prix_global()     → vue d'ensemble boutique
     • analyse_prix_par_vendeur() → qui brade le plus
     • analyse_prix_par_client()  → quels clients obtiennent les meilleurs prix
     • detail_prix_produit()      → historique ligne par ligne d'un article

  B. TENDANCES DE VENTE
     • tendances_ventes()         → progression / déclin par produit
     • produits_en_declin()       → ceux qui décrochent
     • produits_en_croissance()   → ceux qui décollent

Vocabulaire retenu (affiché tel quel à l'utilisateur) :
  • « remise »      = vendu SOUS le prix catalogue  (écart négatif)
  • « majoration »  = vendu AU-DESSUS du prix catalogue (écart positif)
  • « au prix »     = écart inférieur au seuil de tolérance (2 % par défaut)

Toutes les mesures s'appuient sur ventes_details.prix_unitaire (le prix
réellement encaissé) comparé à produits.prix_vente (le prix catalogue), et
sur ventes_details.prix_achat (snapshot du coût au moment de la vente) pour
la marge réelle.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta

from database import get_connection, get_parametres, log_action

# Écart en dessous duquel on considère que le produit est vendu « au prix »
SEUIL_TOLERANCE_PCT = 2.0

# Seuil de variation pour parler de tendance (en %)
SEUIL_TENDANCE_PCT = 15.0


from ui_widgets import parse_float

def _depuis(jours: int) -> str:
    return (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")


def _qualifier(ecart_pct: float, seuil: float = SEUIL_TOLERANCE_PCT) -> str:
    """Qualifie un écart de prix moyen."""
    if ecart_pct < -seuil:
        return "remise"
    if ecart_pct > seuil:
        return "majoration"
    return "au prix"


# ═══════════════════════════════════════════════════════
#  A. PRIX PRATIQUÉS
# ═══════════════════════════════════════════════════════

def _calcul_prix_pratiques(jours: int = 90, min_ventes: int = 1,
                           categorie_id: int | None = None,
                           seuil_tolerance: float = SEUIL_TOLERANCE_PCT) -> list[dict]:
    """
    Pour chaque produit vendu sur la période : compare le prix pratiqué au
    prix catalogue.

    Retourne une liste triée par impact financier décroissant (ce qui coûte
    le plus cher en remises apparaît en premier), avec pour chaque produit :

      prix_catalogue      prix de vente affiché aujourd'hui
      prix_moyen          moyenne pondérée réellement encaissée
      prix_min / prix_max amplitude de négociation
      ecart_moyen         prix_moyen - prix_catalogue (en F CFA, unitaire)
      ecart_pct           idem en pourcentage
      tendance            'remise' | 'majoration' | 'au prix'
      nb_lignes           nombre de lignes de vente
      nb_sous / nb_sur / nb_au_prix   répartition des lignes
      taux_remise_pct     % de lignes vendues sous le catalogue
      impact_total        manque à gagner (négatif) ou bonus (positif) cumulé
      marge_reelle_pct    marge réellement réalisée
      marge_theorique_pct marge si tout avait été vendu au catalogue
      ecart_type          dispersion des prix (cohérence du vendeur)
      alerte              'sous_cout' | 'forte_dispersion' | '' 
    """
    depuis = _depuis(jours)
    conn = get_connection()

    sql = """
        SELECT vd.produit_id, p.reference, p.nom, p.prix_vente AS prix_catalogue,
               COALESCE(p.cump, p.prix_achat) AS cout_actuel,
               c.nom AS categorie_nom,
               vd.quantite, vd.prix_unitaire, vd.prix_achat AS cout_vente,
               v.date_vente, v.client_nom, v.utilisateur
        FROM ventes_details vd
        JOIN ventes v   ON v.id = vd.vente_id
        JOIN produits p ON p.id = vd.produit_id
        LEFT JOIN categories c ON c.id = p.categorie_id
        WHERE v.statut = 'validee' AND date(v.date_vente) >= date(?)
          AND p.prix_vente > 0
    """
    params: list = [depuis]
    if categorie_id:
        sql += " AND p.categorie_id = ?"
        params.append(categorie_id)
    sql += " ORDER BY vd.produit_id, v.date_vente"

    lignes = conn.execute(sql, params).fetchall()
    

    # Regroupement par produit
    groupes: dict[int, dict] = {}
    for l in lignes:
        pid = l["produit_id"]
        g = groupes.setdefault(pid, {
            "produit_id": pid, "reference": l["reference"], "nom": l["nom"],
            "categorie_nom": l["categorie_nom"] or "Sans catégorie",
            "prix_catalogue": parse_float(l["prix_catalogue"]),
            "cout_actuel": parse_float(l["cout_actuel"]),
            "prix": [], "quantites": [], "couts": [],
            "ca": 0.0, "cout_total": 0.0, "qte_totale": 0,
            "nb_sous": 0, "nb_sur": 0, "nb_au_prix": 0,
            "sous_cout": 0,
        })
        pu = parse_float(l["prix_unitaire"])
        qte = int(l["quantite"] or 0)
        catalogue = g["prix_catalogue"]

        g["prix"].append(pu)
        g["quantites"].append(qte)
        g["couts"].append(parse_float(l["cout_vente"]))
        g["ca"] += pu * qte
        g["cout_total"] += parse_float(l["cout_vente"]) * qte
        g["qte_totale"] += qte

        ecart_ligne_pct = ((pu - catalogue) / catalogue * 100) if catalogue else 0
        if ecart_ligne_pct < -seuil_tolerance:
            g["nb_sous"] += 1
        elif ecart_ligne_pct > seuil_tolerance:
            g["nb_sur"] += 1
        else:
            g["nb_au_prix"] += 1

        if pu < parse_float(l["cout_vente"]):
            g["sous_cout"] += 1

    resultat = []
    for g in groupes.values():
        nb_lignes = len(g["prix"])
        if nb_lignes < min_ventes:
            continue
        catalogue = g["prix_catalogue"]
        # Moyenne PONDÉRÉE par les quantités : une ligne de 10 pièces pèse
        # plus qu'une ligne de 1 pièce.
        prix_moyen = g["ca"] / g["qte_totale"] if g["qte_totale"] else 0.0
        ecart_moyen = prix_moyen - catalogue
        ecart_pct = (ecart_moyen / catalogue * 100) if catalogue else 0.0

        # Impact : ce qu'on aurait encaissé au catalogue vs ce qu'on a encaissé
        ca_theorique = catalogue * g["qte_totale"]
        impact_total = g["ca"] - ca_theorique

        marge_reelle = g["ca"] - g["cout_total"]
        marge_reelle_pct = (marge_reelle / g["ca"] * 100) if g["ca"] else 0.0
        cout_moyen = g["cout_total"] / g["qte_totale"] if g["qte_totale"] else 0.0
        marge_theorique_pct = ((catalogue - cout_moyen) / catalogue * 100) if catalogue else 0.0

        ecart_type = statistics.pstdev(g["prix"]) if nb_lignes > 1 else 0.0
        dispersion_pct = (ecart_type / prix_moyen * 100) if prix_moyen else 0.0

        alerte = ""
        if g["sous_cout"]:
            alerte = "sous_cout"
        elif dispersion_pct > 20:
            alerte = "forte_dispersion"

        resultat.append({
            "produit_id": g["produit_id"],
            "reference": g["reference"],
            "nom": g["nom"],
            "categorie_nom": g["categorie_nom"],
            "prix_catalogue": round(catalogue, 2),
            "prix_moyen": round(prix_moyen, 2),
            "prix_min": round(min(g["prix"]), 2),
            "prix_max": round(max(g["prix"]), 2),
            "ecart_moyen": round(ecart_moyen, 2),
            "ecart_pct": round(ecart_pct, 2),
            "tendance": _qualifier(ecart_pct, seuil_tolerance),
            "nb_lignes": nb_lignes,
            "qte_totale": g["qte_totale"],
            "nb_sous": g["nb_sous"],
            "nb_sur": g["nb_sur"],
            "nb_au_prix": g["nb_au_prix"],
            "taux_remise_pct": round(g["nb_sous"] / nb_lignes * 100, 1),
            "taux_majoration_pct": round(g["nb_sur"] / nb_lignes * 100, 1),
            "ca_reel": round(g["ca"], 2),
            "ca_theorique": round(ca_theorique, 2),
            "impact_total": round(impact_total, 2),
            "marge_reelle": round(marge_reelle, 2),
            "marge_reelle_pct": round(marge_reelle_pct, 2),
            "marge_theorique_pct": round(marge_theorique_pct, 2),
            "ecart_type": round(ecart_type, 2),
            "dispersion_pct": round(dispersion_pct, 1),
            "nb_sous_cout": g["sous_cout"],
            "alerte": alerte,
        })

    # Le plus gros manque à gagner d'abord
    resultat.sort(key=lambda x: x["impact_total"])
    return resultat


# ── Cache de l'analyse des prix ──────────────────────────────────────────────
# L'ecran Analyse ouvre trois onglets qui exploitent tous le meme jeu : le
# calcul tournait donc trois fois par affichage (~1,2 s sur 600 ventes).
#
# Invalidation : `total_changes` de la connexion SQLite compte les lignes
# modifiees depuis son ouverture. Il bouge des qu'une vente est enregistree ou
# qu'un prix change, et reste stable sur les lectures — un jeton de version
# gratuit, sans requete supplementaire. Une entree calculee sous une version
# anterieure n'est jamais servie.
#
# Limite assumee : le compteur est propre a CETTE connexion. Si un autre
# processus ecrivait dans la meme base, le cache ne le verrait pas. L'appli
# ouvre une connexion persistante unique, donc le cas ne se presente pas.
_CACHE_PRIX: dict[tuple, list[dict]] = {}


def _version_donnees() -> int:
    try:
        return get_connection().total_changes
    except Exception:
        return -1


def vider_cache_prix() -> None:
    """Purge manuelle du cache (tests, ou reprise de donnees externe)."""
    _CACHE_PRIX.clear()


def analyse_prix_pratiques(jours: int = 90, min_ventes: int = 1,
                           categorie_id: int | None = None,
                           seuil_tolerance: float = SEUIL_TOLERANCE_PCT) -> list[dict]:
    """Analyse des prix pratiques, memoisee tant que les donnees n'ont pas bouge."""
    cle = (jours, min_ventes, categorie_id, seuil_tolerance, _version_donnees())
    resultat = _CACHE_PRIX.get(cle)
    if resultat is None:
        resultat = _calcul_prix_pratiques(jours, min_ventes, categorie_id,
                                          seuil_tolerance)
        # Une seule version vit a la fois : les cles obsoletes ne servent plus.
        _CACHE_PRIX.clear()
        _CACHE_PRIX[cle] = resultat
    # Copie de la liste : un appelant qui trie ou filtre ne doit pas corrompre
    # l'entree en cache pour les suivants.
    return list(resultat)


def synthese_prix_global(jours: int = 90,
                         seuil_tolerance: float = SEUIL_TOLERANCE_PCT) -> dict:
    """
    Vue d'ensemble : la boutique a-t-elle tendance à brader ou à majorer ?
    Réponse en une phrase + les chiffres qui la soutiennent.
    """
    produits = analyse_prix_pratiques(jours, min_ventes=1,
                                      seuil_tolerance=seuil_tolerance)
    if not produits:
        return {
            "periode_jours": jours, "nb_produits": 0, "nb_lignes": 0,
            "ca_reel": 0.0, "ca_theorique": 0.0, "impact_total": 0.0,
            "impact_pct": 0.0, "ecart_moyen_pct": 0.0, "tendance": "aucune donnée",
            "verdict": "Pas encore assez de ventes pour analyser les prix pratiqués.",
            "nb_remise": 0, "nb_majoration": 0, "nb_au_prix": 0,
            "lignes_sous": 0, "lignes_sur": 0, "lignes_au_prix": 0,
            "taux_negociation_pct": 0.0, "marge_reelle_pct": 0.0,
            "marge_theorique_pct": 0.0, "marge_perdue": 0.0,
            "nb_alertes_sous_cout": 0, "top_remises": [], "top_majorations": [],
        }

    ca_reel = sum(p["ca_reel"] for p in produits)
    ca_theorique = sum(p["ca_theorique"] for p in produits)
    impact = ca_reel - ca_theorique
    nb_lignes = sum(p["nb_lignes"] for p in produits)
    lignes_sous = sum(p["nb_sous"] for p in produits)
    lignes_sur = sum(p["nb_sur"] for p in produits)
    lignes_au_prix = sum(p["nb_au_prix"] for p in produits)

    marge_reelle = sum(p["marge_reelle"] for p in produits)
    marge_reelle_pct = (marge_reelle / ca_reel * 100) if ca_reel else 0.0
    # Marge théorique : même coût, mais au prix catalogue
    cout_total = ca_reel - marge_reelle
    marge_theo = ca_theorique - cout_total
    marge_theorique_pct = (marge_theo / ca_theorique * 100) if ca_theorique else 0.0

    ecart_moyen_pct = (impact / ca_theorique * 100) if ca_theorique else 0.0
    tendance = _qualifier(ecart_moyen_pct, seuil_tolerance)

    if tendance == "remise":
        verdict = (f"Vous vendez en moyenne {abs(ecart_moyen_pct):.1f} % SOUS "
                   f"votre prix catalogue. Manque à gagner sur {jours} jours : "
                   f"{abs(impact):,.0f} F CFA.")
    elif tendance == "majoration":
        verdict = (f"Vous vendez en moyenne {ecart_moyen_pct:.1f} % AU-DESSUS "
                   f"de votre prix catalogue. Bonus sur {jours} jours : "
                   f"+{impact:,.0f} F CFA. Vos prix affichés sont peut-être "
                   f"trop bas.")
    else:
        verdict = (f"Vos prix pratiqués collent au catalogue "
                   f"({ecart_moyen_pct:+.1f} %). Bonne discipline tarifaire.")

    return {
        "periode_jours": jours,
        "nb_produits": len(produits),
        "nb_lignes": nb_lignes,
        "ca_reel": round(ca_reel, 2),
        "ca_theorique": round(ca_theorique, 2),
        "impact_total": round(impact, 2),
        "impact_pct": round(ecart_moyen_pct, 2),
        "ecart_moyen_pct": round(ecart_moyen_pct, 2),
        "tendance": tendance,
        "verdict": verdict,
        "nb_remise": sum(1 for p in produits if p["tendance"] == "remise"),
        "nb_majoration": sum(1 for p in produits if p["tendance"] == "majoration"),
        "nb_au_prix": sum(1 for p in produits if p["tendance"] == "au prix"),
        "lignes_sous": lignes_sous,
        "lignes_sur": lignes_sur,
        "lignes_au_prix": lignes_au_prix,
        "taux_negociation_pct": round((lignes_sous + lignes_sur) / nb_lignes * 100, 1)
                                if nb_lignes else 0.0,
        "marge_reelle_pct": round(marge_reelle_pct, 2),
        "marge_theorique_pct": round(marge_theorique_pct, 2),
        "marge_perdue": round(marge_theo - marge_reelle, 2),
        "nb_alertes_sous_cout": sum(1 for p in produits if p["nb_sous_cout"]),
        "top_remises": produits[:5],
        "top_majorations": sorted(produits, key=lambda x: -x["impact_total"])[:5],
    }


def analyse_prix_par_vendeur(jours: int = 90) -> list[dict]:
    """Qui brade, qui tient les prix ? Utile pour former l'équipe."""
    depuis = _depuis(jours)
    conn = get_connection()
    lignes = conn.execute("""
        SELECT COALESCE(NULLIF(v.utilisateur,''),'(non renseigné)') AS vendeur,
               vd.quantite, vd.prix_unitaire, vd.prix_achat,
               p.prix_vente AS prix_catalogue
        FROM ventes_details vd
        JOIN ventes v   ON v.id = vd.vente_id
        JOIN produits p ON p.id = vd.produit_id
        WHERE v.statut='validee' AND date(v.date_vente) >= date(?)
          AND p.prix_vente > 0""", (depuis,)).fetchall()
    

    par_vendeur: dict[str, dict] = {}
    for l in lignes:
        v = par_vendeur.setdefault(l["vendeur"], {
            "vendeur": l["vendeur"], "nb_lignes": 0, "qte": 0,
            "ca_reel": 0.0, "ca_theorique": 0.0, "cout": 0.0,
            "nb_sous": 0, "nb_sur": 0, "nb_sous_cout": 0})
        qte = int(l["quantite"] or 0)
        pu = parse_float(l["prix_unitaire"])
        cat = parse_float(l["prix_catalogue"])
        v["nb_lignes"] += 1
        v["qte"] += qte
        v["ca_reel"] += pu * qte
        v["ca_theorique"] += cat * qte
        v["cout"] += parse_float(l["prix_achat"]) * qte
        ecart = ((pu - cat) / cat * 100) if cat else 0
        if ecart < -SEUIL_TOLERANCE_PCT:
            v["nb_sous"] += 1
        elif ecart > SEUIL_TOLERANCE_PCT:
            v["nb_sur"] += 1
        if pu < parse_float(l["prix_achat"]):
            v["nb_sous_cout"] += 1

    resultat = []
    for v in par_vendeur.values():
        impact = v["ca_reel"] - v["ca_theorique"]
        ecart_pct = (impact / v["ca_theorique"] * 100) if v["ca_theorique"] else 0.0
        marge = v["ca_reel"] - v["cout"]
        resultat.append({
            **v,
            "ca_reel": round(v["ca_reel"], 2),
            "ca_theorique": round(v["ca_theorique"], 2),
            "impact_total": round(impact, 2),
            "ecart_pct": round(ecart_pct, 2),
            "tendance": _qualifier(ecart_pct),
            "marge": round(marge, 2),
            "marge_pct": round(marge / v["ca_reel"] * 100, 2) if v["ca_reel"] else 0.0,
            "taux_remise_pct": round(v["nb_sous"] / v["nb_lignes"] * 100, 1)
                               if v["nb_lignes"] else 0.0,
        })
    resultat.sort(key=lambda x: x["impact_total"])
    return resultat


def analyse_prix_par_client(jours: int = 180, min_lignes: int = 2) -> list[dict]:
    """
    Quels clients obtiennent systématiquement les meilleurs prix ?
    Permet de repérer les gros négociateurs et d'ajuster.
    """
    depuis = _depuis(jours)
    conn = get_connection()
    lignes = conn.execute("""
        SELECT COALESCE(c.nom, v.client_nom, 'Client') AS client,
               v.client_id, COALESCE(c.type_client,'particulier') AS type_client,
               vd.quantite, vd.prix_unitaire, vd.prix_achat,
               p.prix_vente AS prix_catalogue
        FROM ventes_details vd
        JOIN ventes v   ON v.id = vd.vente_id
        JOIN produits p ON p.id = vd.produit_id
        LEFT JOIN clients c ON c.id = v.client_id
        WHERE v.statut='validee' AND date(v.date_vente) >= date(?)
          AND p.prix_vente > 0""", (depuis,)).fetchall()
    

    par_client: dict[str, dict] = {}
    for l in lignes:
        cle = l["client"]
        c = par_client.setdefault(cle, {
            "client": cle, "client_id": l["client_id"],
            "type_client": l["type_client"], "nb_lignes": 0, "qte": 0,
            "ca_reel": 0.0, "ca_theorique": 0.0, "cout": 0.0, "nb_sous": 0})
        qte = int(l["quantite"] or 0)
        pu = parse_float(l["prix_unitaire"])
        cat = parse_float(l["prix_catalogue"])
        c["nb_lignes"] += 1
        c["qte"] += qte
        c["ca_reel"] += pu * qte
        c["ca_theorique"] += cat * qte
        c["cout"] += parse_float(l["prix_achat"]) * qte
        if cat and (pu - cat) / cat * 100 < -SEUIL_TOLERANCE_PCT:
            c["nb_sous"] += 1

    resultat = []
    for c in par_client.values():
        if c["nb_lignes"] < min_lignes:
            continue
        impact = c["ca_reel"] - c["ca_theorique"]
        ecart_pct = (impact / c["ca_theorique"] * 100) if c["ca_theorique"] else 0.0
        marge = c["ca_reel"] - c["cout"]
        resultat.append({
            **c,
            "ca_reel": round(c["ca_reel"], 2),
            "ca_theorique": round(c["ca_theorique"], 2),
            "impact_total": round(impact, 2),
            "ecart_pct": round(ecart_pct, 2),
            "tendance": _qualifier(ecart_pct),
            "remise_moyenne_pct": round(-ecart_pct, 2),
            "marge": round(marge, 2),
            "marge_pct": round(marge / c["ca_reel"] * 100, 2) if c["ca_reel"] else 0.0,
            "taux_remise_pct": round(c["nb_sous"] / c["nb_lignes"] * 100, 1),
        })
    resultat.sort(key=lambda x: x["impact_total"])
    return resultat


def detail_prix_produit(produit_id: int, jours: int = 365) -> dict:
    """
    Historique détaillé des prix pratiqués pour UN produit.
    Sert au panneau de détail de l'écran d'analyse.
    """
    depuis = _depuis(jours)
    conn = get_connection()
    produit = conn.execute(
        """SELECT reference, nom, prix_vente, COALESCE(cump, prix_achat) AS cout
           FROM produits WHERE id=?""", (produit_id,)).fetchone()
    if not produit:
        
        return {"produit": None, "lignes": [], "paliers": []}

    lignes = conn.execute("""
        SELECT v.numero, v.date_vente, v.client_nom, v.utilisateur,
               vd.quantite, vd.prix_unitaire, vd.prix_achat, vd.total
        FROM ventes_details vd JOIN ventes v ON v.id = vd.vente_id
        WHERE vd.produit_id = ? AND v.statut='validee'
          AND date(v.date_vente) >= date(?)
        ORDER BY v.date_vente DESC""", (produit_id, depuis)).fetchall()
    

    catalogue = parse_float(produit["prix_vente"])
    detail = []
    for l in lignes:
        pu = parse_float(l["prix_unitaire"])
        ecart = pu - catalogue
        detail.append({
            "numero": l["numero"], "date_vente": l["date_vente"],
            "client_nom": l["client_nom"], "utilisateur": l["utilisateur"],
            "quantite": l["quantite"], "prix_unitaire": pu,
            "cout": parse_float(l["prix_achat"]), "total": parse_float(l["total"]),
            "ecart": round(ecart, 2),
            "ecart_pct": round(ecart / catalogue * 100, 2) if catalogue else 0.0,
            "marge_unitaire": round(pu - parse_float(l["prix_achat"]), 2),
            "sous_cout": pu < parse_float(l["prix_achat"]),
        })

    # Paliers de prix : quels prix reviennent le plus souvent ?
    compteur: dict[float, int] = {}
    for d in detail:
        compteur[d["prix_unitaire"]] = compteur.get(d["prix_unitaire"], 0) + 1
    paliers = [{"prix": prix, "nb": nb,
                "part_pct": round(nb / len(detail) * 100, 1) if detail else 0.0}
               for prix, nb in sorted(compteur.items(), key=lambda x: -x[1])]

    return {
        "produit": {"reference": produit["reference"], "nom": produit["nom"],
                    "prix_catalogue": catalogue, "cout": parse_float(produit["cout"])},
        "lignes": detail,
        "paliers": paliers[:8],
    }


def prix_conseille(produit_id: int, jours: int = 90,
                   marge_cible_pct: float | None = None) -> dict:
    """
    Suggère un prix catalogue réaliste à partir des prix réellement pratiqués.

    Logique : si 80 % des ventes se font à un prix donné, c'est CE prix que le
    marché accepte — le catalogue devrait s'en approcher. On vérifie ensuite
    que la marge reste acceptable.
    """
    detail = detail_prix_produit(produit_id, jours)
    if not detail["produit"] or not detail["lignes"]:
        return {"possible": False,
                "message": "Pas assez de ventes récentes pour conseiller un prix."}

    p = detail["produit"]
    prix = [l["prix_unitaire"] for l in detail["lignes"]]
    catalogue = p["prix_catalogue"]
    cout = p["cout"]

    median = statistics.median(prix)
    # Prix le plus fréquemment pratiqué
    palier_dominant = detail["paliers"][0] if detail["paliers"] else None

    if marge_cible_pct is None:
        marge_cible_pct = parse_float(get_parametres().get("marge_cible_pct", 30), 30)
    prix_plancher = cout * (1 + marge_cible_pct / 100) if cout else 0

    conseil = max(median, prix_plancher)
    ecart_vs_catalogue = conseil - catalogue

    if abs(ecart_vs_catalogue) < catalogue * 0.02:
        message = (f"Votre prix catalogue ({catalogue:,.0f}) est cohérent avec "
                   f"le marché (médiane {median:,.0f}).")
    elif conseil < catalogue:
        message = (f"Le marché paie plutôt {median:,.0f} que {catalogue:,.0f}. "
                   f"Baisser le catalogue à {conseil:,.0f} rendrait vos remises "
                   f"inutiles et vos marges lisibles.")
    else:
        message = (f"Vous vendez régulièrement au-dessus du catalogue "
                   f"(médiane {median:,.0f} vs {catalogue:,.0f}). "
                   f"Vous pouvez monter le catalogue à {conseil:,.0f}.")

    if prix_plancher > median and cout:
        message += (f"\n⚠ Attention : sous {prix_plancher:,.0f} vous passez "
                    f"sous {marge_cible_pct:.0f} % de marge.")

    return {
        "possible": True,
        "prix_catalogue": catalogue,
        "prix_median": round(median, 2),
        "prix_moyen": round(sum(prix) / len(prix), 2),
        "prix_min": min(prix),
        "prix_max": max(prix),
        "palier_dominant": palier_dominant,
        "cout": cout,
        "prix_plancher": round(prix_plancher, 2),
        "marge_cible_pct": marge_cible_pct,
        "prix_conseille": round(conseil, 2),
        "ecart_vs_catalogue": round(ecart_vs_catalogue, 2),
        "nb_ventes": len(prix),
        "message": message,
    }


# ═══════════════════════════════════════════════════════
#  B. TENDANCES DE VENTE
# ═══════════════════════════════════════════════════════

def tendances_ventes(fenetre_jours: int = 30, min_qte: int = 1) -> list[dict]:
    """
    Compare la période récente (N derniers jours) à la période précédente
    (les N jours d'avant) pour chaque produit.

    Retourne pour chaque produit :
      qte_recente / qte_precedente     quantités vendues
      ca_recent / ca_precedent         chiffre d'affaires
      variation_qte_pct                progression en volume
      variation_ca_pct                 progression en valeur
      tendance      'forte_hausse' | 'hausse' | 'stable' | 'baisse'
                    | 'forte_baisse' | 'nouveau' | 'arrete'
      libelle       version lisible en français
    """
    fin_recente = datetime.now()
    debut_recente = fin_recente - timedelta(days=fenetre_jours)
    debut_precedente = debut_recente - timedelta(days=fenetre_jours)

    conn = get_connection()
    lignes = conn.execute("""
        SELECT p.id AS produit_id, p.reference, p.nom, p.prix_vente, p.stock,
               p.stock_vente, COALESCE(p.cump, p.prix_achat) AS cout,
               c.nom AS categorie_nom,
               COALESCE(SUM(CASE WHEN date(v.date_vente) >= date(?)
                                 THEN vd.quantite ELSE 0 END), 0) AS qte_recente,
               COALESCE(SUM(CASE WHEN date(v.date_vente) >= date(?)
                                  AND date(v.date_vente) < date(?)
                                 THEN vd.quantite ELSE 0 END), 0) AS qte_precedente,
               COALESCE(SUM(CASE WHEN date(v.date_vente) >= date(?)
                                 THEN vd.total ELSE 0 END), 0) AS ca_recent,
               COALESCE(SUM(CASE WHEN date(v.date_vente) >= date(?)
                                  AND date(v.date_vente) < date(?)
                                 THEN vd.total ELSE 0 END), 0) AS ca_precedent,
               MAX(v.date_vente) AS derniere_vente
        FROM produits p
        LEFT JOIN ventes_details vd ON vd.produit_id = p.id
        LEFT JOIN ventes v ON v.id = vd.vente_id AND v.statut = 'validee'
        LEFT JOIN categories c ON c.id = p.categorie_id
        WHERE p.actif = 1
        GROUP BY p.id
        HAVING qte_recente > 0 OR qte_precedente > 0
    """, (debut_recente.strftime("%Y-%m-%d"),
          debut_precedente.strftime("%Y-%m-%d"), debut_recente.strftime("%Y-%m-%d"),
          debut_recente.strftime("%Y-%m-%d"),
          debut_precedente.strftime("%Y-%m-%d"), debut_recente.strftime("%Y-%m-%d"))
    ).fetchall()
    

    resultat = []
    for l in lignes:
        qr = int(l["qte_recente"] or 0)
        qp = int(l["qte_precedente"] or 0)
        if max(qr, qp) < min_qte:
            continue
        car = parse_float(l["ca_recent"])
        cap = parse_float(l["ca_precedent"])

        if qp == 0 and qr > 0:
            var_qte, tendance = 100.0, "nouveau"
            libelle = "🆕 Nouveau / reprise"
        elif qr == 0 and qp > 0:
            var_qte, tendance = -100.0, "arrete"
            libelle = "⛔ Ne se vend plus"
        else:
            var_qte = (qr - qp) / qp * 100
            if var_qte >= 50:
                tendance, libelle = "forte_hausse", "🚀 Forte hausse"
            elif var_qte >= SEUIL_TENDANCE_PCT:
                tendance, libelle = "hausse", "📈 En hausse"
            elif var_qte <= -50:
                tendance, libelle = "forte_baisse", "📉 Forte baisse"
            elif var_qte <= -SEUIL_TENDANCE_PCT:
                tendance, libelle = "baisse", "↘️ En baisse"
            else:
                tendance, libelle = "stable", "➡️ Stable"

        var_ca = ((car - cap) / cap * 100) if cap else (100.0 if car else 0.0)

        resultat.append({
            "produit_id": l["produit_id"],
            "reference": l["reference"],
            "nom": l["nom"],
            "categorie_nom": l["categorie_nom"] or "Sans catégorie",
            "prix_vente": parse_float(l["prix_vente"]),
            "cout": parse_float(l["cout"]),
            "stock": l["stock"] or 0,
            "stock_vente": l["stock_vente"] or 0,
            "qte_recente": qr,
            "qte_precedente": qp,
            "ca_recent": round(car, 2),
            "ca_precedent": round(cap, 2),
            "variation_qte": qr - qp,
            "variation_qte_pct": round(var_qte, 1),
            "variation_ca_pct": round(var_ca, 1),
            "tendance": tendance,
            "libelle": libelle,
            "derniere_vente": l["derniere_vente"],
            "capital_immobilise": round((l["stock"] or 0) * parse_float(l["cout"]), 2),
        })

    # Les plus fortes variations en premier, en valeur absolue
    ordre = {"forte_baisse": 0, "arrete": 1, "baisse": 2, "forte_hausse": 3,
             "nouveau": 4, "hausse": 5, "stable": 6}
    resultat.sort(key=lambda x: (ordre.get(x["tendance"], 9), -abs(x["variation_qte_pct"])))
    return resultat


def produits_en_declin(fenetre_jours: int = 30, seuil_pct: float = SEUIL_TENDANCE_PCT,
                       min_qte: int = 1) -> list[dict]:
    """
    Produits qui se vendent de MOINS en moins — à surveiller de près :
    risque de stock mort et de capital immobilisé.
    """
    tous = tendances_ventes(fenetre_jours, min_qte)
    declin = [t for t in tous
              if t["tendance"] in ("baisse", "forte_baisse", "arrete")
              and t["variation_qte_pct"] <= -seuil_pct]
    # Priorité : ceux qui immobilisent le plus d'argent
    declin.sort(key=lambda x: -x["capital_immobilise"])
    return declin


def produits_en_croissance(fenetre_jours: int = 30,
                           seuil_pct: float = SEUIL_TENDANCE_PCT,
                           min_qte: int = 1) -> list[dict]:
    """
    Produits qui se vendent de PLUS en plus — à ne surtout pas laisser
    tomber en rupture, et candidats à une hausse de prix.
    """
    tous = tendances_ventes(fenetre_jours, min_qte)
    hausse = [t for t in tous
              if t["tendance"] in ("hausse", "forte_hausse", "nouveau")
              and t["variation_qte_pct"] >= seuil_pct]
    hausse.sort(key=lambda x: -x["variation_qte_pct"])
    return hausse


def alertes_commerciales(fenetre_jours: int = 30) -> list[dict]:
    """
    Liste unifiée et priorisée des signaux à traiter, pour le tableau de bord.
    Chaque alerte : niveau, categorie, titre, detail, produit_id (option).
    """
    alertes = []

    # ── 1. Ventes à perte (le plus grave) ──
    prix = analyse_prix_pratiques(jours=fenetre_jours * 3, min_ventes=1)
    for p in prix:
        if p["nb_sous_cout"]:
            alertes.append({
                "niveau": "critique",
                "categorie": "Vente à perte",
                "titre": f"{p['nom']} vendu sous son coût",
                "detail": (f"{p['nb_sous_cout']} vente(s) en dessous du prix de "
                           f"revient. Prix mini pratiqué {p['prix_min']:,.0f} "
                           f"pour un coût de revient supérieur."),
                "produit_id": p["produit_id"],
                "impact": p["impact_total"],
            })

    # ── 2. Remises massives ──
    for p in prix[:12]:
        if p["tendance"] == "remise" and p["ecart_pct"] <= -10 and p["nb_lignes"] >= 2:
            alertes.append({
                "niveau": "haute",
                "categorie": "Remise excessive",
                "titre": f"{p['nom']} bradé de {abs(p['ecart_pct']):.0f} %",
                "detail": (f"Catalogue {p['prix_catalogue']:,.0f}, pratiqué en "
                           f"moyenne {p['prix_moyen']:,.0f} sur {p['nb_lignes']} "
                           f"vente(s). Manque à gagner {abs(p['impact_total']):,.0f}."),
                "produit_id": p["produit_id"],
                "impact": p["impact_total"],
            })

    # ── 3. Prix catalogue trop bas ──
    for p in sorted(prix, key=lambda x: -x["impact_total"])[:8]:
        if p["tendance"] == "majoration" and p["ecart_pct"] >= 10 and p["nb_lignes"] >= 2:
            alertes.append({
                "niveau": "info",
                "categorie": "Prix catalogue trop bas",
                "titre": f"{p['nom']} vendu +{p['ecart_pct']:.0f} % au-dessus",
                "detail": (f"Le marché accepte {p['prix_moyen']:,.0f} alors que "
                           f"votre catalogue affiche {p['prix_catalogue']:,.0f}. "
                           f"Pensez à réviser le prix affiché."),
                "produit_id": p["produit_id"],
                "impact": p["impact_total"],
            })

    # ── 4. Produits en déclin avec du stock ──
    for t in produits_en_declin(fenetre_jours)[:10]:
        if t["capital_immobilise"] > 0:
            alertes.append({
                "niveau": "haute" if t["tendance"] in ("forte_baisse", "arrete") else "moyenne",
                "categorie": "Ventes en baisse",
                "titre": f"{t['nom']} : {t['libelle']}",
                "detail": (f"{t['qte_precedente']} → {t['qte_recente']} unité(s) "
                           f"({t['variation_qte_pct']:+.0f} %). "
                           f"{t['stock']} en stock = "
                           f"{t['capital_immobilise']:,.0f} immobilisés."),
                "produit_id": t["produit_id"],
                "impact": -t["capital_immobilise"],
            })

    # ── 5. Produits en forte croissance à risque de rupture ──
    for t in produits_en_croissance(fenetre_jours)[:10]:
        if t["stock_vente"] <= t["qte_recente"]:
            alertes.append({
                "niveau": "haute",
                "categorie": "Croissance à sécuriser",
                "titre": f"{t['nom']} : {t['libelle']}",
                "detail": (f"{t['qte_precedente']} → {t['qte_recente']} unité(s) "
                           f"({t['variation_qte_pct']:+.0f} %) mais seulement "
                           f"{t['stock_vente']} en rayon. Risque de rupture "
                           f"sur un produit qui décolle."),
                "produit_id": t["produit_id"],
                "impact": t["ca_recent"],
            })

    ordre = {"critique": 0, "haute": 1, "moyenne": 2, "info": 3}
    alertes.sort(key=lambda a: (ordre.get(a["niveau"], 9), -abs(a.get("impact", 0))))
    return alertes


# ═══════════════════════════════════════════════════════
#  EXPORTS
# ═══════════════════════════════════════════════════════

def exporter_analyse_prix(jours: int = 90) -> str:
    """Export CSV de l'analyse des prix pratiqués."""
    from database import export_csv
    donnees = analyse_prix_pratiques(jours)
    lignes = [[
        p["reference"], p["nom"], p["categorie_nom"],
        f"{p['prix_catalogue']:.0f}", f"{p['prix_moyen']:.0f}",
        f"{p['prix_min']:.0f}", f"{p['prix_max']:.0f}",
        f"{p['ecart_moyen']:.0f}", f"{p['ecart_pct']:.1f}",
        {"remise": "Remise", "majoration": "Majoration",
         "au prix": "Au prix"}[p["tendance"]],
        p["nb_lignes"], p["qte_totale"], p["nb_sous"], p["nb_sur"], p["nb_au_prix"],
        f"{p['taux_remise_pct']:.0f}", f"{p['ca_reel']:.0f}",
        f"{p['ca_theorique']:.0f}", f"{p['impact_total']:.0f}",
        f"{p['marge_reelle_pct']:.1f}", f"{p['marge_theorique_pct']:.1f}",
        p["nb_sous_cout"],
    ] for p in donnees]
    return export_csv(
        f"analyse_prix_{datetime.now():%Y%m%d_%H%M}.csv",
        ["Référence", "Produit", "Catégorie", "Prix catalogue", "Prix moyen réel",
         "Prix mini", "Prix maxi", "Écart moyen", "Écart %", "Tendance",
         "Nb ventes", "Qté vendue", "Lignes sous prix", "Lignes sur prix",
         "Lignes au prix", "% remisé", "CA réel", "CA au catalogue",
         "Impact", "Marge réelle %", "Marge théorique %", "Ventes à perte"],
        lignes)


def exporter_tendances(fenetre_jours: int = 30) -> str:
    """Export CSV des tendances de vente."""
    from database import export_csv
    donnees = tendances_ventes(fenetre_jours)
    lignes = [[
        t["reference"], t["nom"], t["categorie_nom"], t["libelle"],
        t["qte_precedente"], t["qte_recente"], t["variation_qte"],
        f"{t['variation_qte_pct']:.0f}", f"{t['ca_precedent']:.0f}",
        f"{t['ca_recent']:.0f}", f"{t['variation_ca_pct']:.0f}",
        t["stock"], f"{t['capital_immobilise']:.0f}",
        t["derniere_vente"] or "",
    ] for t in donnees]
    return export_csv(
        f"tendances_ventes_{datetime.now():%Y%m%d_%H%M}.csv",
        ["Référence", "Produit", "Catégorie", "Tendance",
         f"Qté {fenetre_jours}j précédents", f"Qté {fenetre_jours}j récents",
         "Variation qté", "Variation %", "CA précédent", "CA récent",
         "Variation CA %", "Stock", "Capital immobilisé", "Dernière vente"],
        lignes)


if __name__ == "__main__":
    print("=== SYNTHÈSE DES PRIX PRATIQUÉS ===")
    s = synthese_prix_global(90)
    print(s["verdict"])
    print(f"\nCA réel      : {s['ca_reel']:,.0f}")
    print(f"CA catalogue : {s['ca_theorique']:,.0f}")
    print(f"Impact       : {s['impact_total']:+,.0f} ({s['impact_pct']:+.1f} %)")
    print(f"Négociation  : {s['taux_negociation_pct']:.0f} % des lignes")
    print(f"Marge réelle : {s['marge_reelle_pct']:.1f} % "
          f"(théorique {s['marge_theorique_pct']:.1f} %)")

    print("\n=== TENDANCES ===")
    for t in tendances_ventes(30)[:10]:
        print(f"  {t['libelle']:22} {t['nom'][:34]:34} "
              f"{t['qte_precedente']:>4} → {t['qte_recente']:>4} "
              f"({t['variation_qte_pct']:+.0f} %)")

    print("\n=== ALERTES COMMERCIALES ===")
    for a in alertes_commerciales(30)[:10]:
        print(f"  [{a['niveau']:8}] {a['categorie']:26} {a['titre']}")
