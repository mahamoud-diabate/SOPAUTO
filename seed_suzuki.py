import sqlite3
import database as db

def reinitialiser_et_inserer_suzuki():
    db.init_database()
    conn = db.get_connection()
    cursor = conn.cursor()

    # 1. Vidage complet des données (historique et produits)
    cursor.execute("PRAGMA foreign_keys = OFF")
    tables_a_vider = [
        "ventes_details", "ventes", "mouvements_stock", "stock_depot",
        "commandes_details", "commandes", "inventaires", "journal",
        "retours_details", "retours", "reglements", "creances",
        "vehicule_compatibilite", "references_croisees", "prix_historique",
        "produits"
    ]
    for t in tables_a_vider:
        try:
            cursor.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass
    try:
        cursor.execute("DELETE FROM sqlite_sequence")
    except sqlite3.OperationalError:
        pass
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    # Catégories requises
    cats = {row["nom"]: row["id"] for row in conn.execute("SELECT id, nom FROM categories").fetchall()}

    # Supplier ID
    fournisseur = conn.execute("SELECT id FROM fournisseurs LIMIT 1").fetchone()
    fournisseur_id = fournisseur["id"] if fournisseur else None
    if not fournisseur_id:
        cursor.execute("INSERT INTO fournisseurs (nom, contact) VALUES ('Suzuki Auto Parts', '0102030405')")
        fournisseur_id = cursor.lastrowid

    # Dépôt par défaut
    depot = conn.execute("SELECT id FROM depots WHERE par_defaut=1").fetchone()
    depot_id = depot["id"] if depot else 1

    # 2. Liste de 20 pièces Suzuki
    pieces_suzuki = [
        ("Plaquettes de frein Avant Suzuki Swift / Alto", "Freinage", "SUZ-FRN-001", "33061-M79F00", 8500, 15000, 20, 5, "Suzuki Swift IV / Alto VIII"),
        ("Disque de frein ventilé Avant Suzuki Grand Vitara", "Freinage", "SUZ-FRN-002", "55311-65J00", 18000, 32000, 12, 3, "Suzuki Grand Vitara II"),
        ("Filtre à huile Suzuki Swift / Jimny / Vitara 1.3/1.5", "Filtres", "SUZ-FLT-001", "16510-61A31", 2200, 4500, 40, 10, "Suzuki Swift / Jimny / Vitara"),
        ("Filtre à air moteur Suzuki Grand Vitara II 2.0L", "Filtres", "SUZ-FLT-002", "13780-65J00", 3500, 7000, 25, 5, "Suzuki Grand Vitara II"),
        ("Filtre d'habitacle Suzuki Celerio / Swift", "Filtres", "SUZ-FLT-003", "95860-68L00", 2800, 5500, 30, 5, "Suzuki Celerio / Swift"),
        ("Amortisseur Avant Droit Suzuki Jimny 1.3 4WD", "Suspension", "SUZ-SUS-001", "41601-81A00", 24000, 42000, 10, 2, "Suzuki Jimny 4WD"),
        ("Amortisseur Arrière Suzuki Grand Vitara", "Suspension", "SUZ-SUS-002", "41800-65J00", 19500, 35000, 14, 4, "Suzuki Grand Vitara II"),
        ("Kit d'embrayage complet Suzuki Swift III 1.3", "Transmission", "SUZ-TRM-001", "22100-63J00", 42000, 75000, 8, 2, "Suzuki Swift III"),
        ("Courroie d'accessoires Suzuki Vitara 1.6 VVT", "Moteur", "SUZ-MOT-001", "95141-60J00", 4500, 9000, 20, 5, "Suzuki Vitara / Swift"),
        ("Kit de distribution avec pompe à eau Suzuki Carry 1.3", "Moteur", "SUZ-MOT-002", "12760-77A00", 32000, 58000, 6, 2, "Suzuki Carry / APV"),
        ("Bougie d'allumage Iridium Suzuki Swift Sport / Vitara", "Électricité", "SUZ-ELE-001", "09482-00547", 3200, 6500, 50, 10, "Suzuki Swift / Vitara"),
        ("Rotule de direction Extérieure Suzuki Alto / Celerio", "Suspension", "SUZ-SUS-003", "48810-68H00", 5500, 11000, 18, 4, "Suzuki Alto / Celerio"),
        ("Cardan de transmission Droit Suzuki Jimny", "Transmission", "SUZ-TRM-002", "44101-81A00", 38000, 68000, 6, 2, "Suzuki Jimny 1.3"),
        ("Pompe à eau moteur Suzuki Grand Vitara 2.0", "Moteur", "SUZ-MOT-003", "17400-77815", 16500, 30000, 10, 3, "Suzuki Grand Vitara"),
        ("Rétroviseur extérieur Électrique Droit Suzuki Swift", "Carrosserie", "SUZ-CAR-001", "84701-68L00", 22000, 40000, 5, 2, "Suzuki Swift IV"),
        ("Optique de phare Avant Gauche Suzuki Alto VIII", "Éclairage", "SUZ-ECL-001", "35320-79M00", 28000, 52000, 4, 1, "Suzuki Alto VIII"),
        ("Radiateur de refroidissement moteur Suzuki Swift 1.2", "Moteur", "SUZ-MOT-004", "17700-68L00", 35000, 62000, 5, 1, "Suzuki Swift 1.2"),
        ("Balai d'essuie-glace Avant Suzuki Vitara (Paire)", "Carrosserie", "SUZ-CAR-002", "38340-54P00", 4000, 8000, 25, 5, "Suzuki Vitara / S-Cross"),
        ("Capteur de vitesse ABS Avant Suzuki SX4 / S-Cross", "Électricité", "SUZ-ELE-002", "56210-79J00", 9500, 18000, 12, 3, "Suzuki SX4 / S-Cross"),
        ("Thermostat d'eau 82°C Suzuki Swift / Jimny / Vitara", "Moteur", "SUZ-MOT-005", "17670-66D00", 4500, 9500, 15, 3, "Suzuki Swift / Jimny")
    ]

    # Insertion des 20 produits via add_produit
    for nom, cat_nom, ref, oem, prix_achat, prix_vente, stock_qte, stock_mini, comp_vehicule in pieces_suzuki:
        cat_id = cats.get(cat_nom, 1)

        ok, msg = db.add_produit(
            reference=ref,
            nom=nom,
            description=f"Pièce d'origine Suzuki compatible {comp_vehicule}. Réf OEM: {oem}",
            categorie_id=cat_id,
            fournisseur_id=fournisseur_id,
            marque="Suzuki",
            prix_achat=prix_achat,
            prix_vente=prix_vente,
            stock_reserve=0,
            stock_vente=stock_qte,
            stock_mini=stock_mini,
            code_barres=oem
        )

    conn.commit()
    print("SUCCES : 20 pièces Suzuki insérées.")

if __name__ == "__main__":
    reinitialiser_et_inserer_suzuki()
