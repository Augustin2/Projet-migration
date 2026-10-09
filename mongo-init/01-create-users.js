// Exécuté automatiquement au premier démarrage du conteneur (volume vide).
// Les mots de passe viennent des variables d'environnement : aucun secret dans le code.

const dbName = process.env.MONGO_DB || "healthcare";
const appDb = db.getSiblingDB(dbName);

// 1. Compte du script de migration : lecture + écriture
appDb.createUser({
  user: "migration_user",
  pwd: process.env.MIGRATION_PASSWORD,
  roles: [{ role: "readWrite", db: dbName }]
});

// 2. Compte analyste : lecture seule
appDb.createUser({
  user: "analyst_user",
  pwd: process.env.ANALYST_PASSWORD,
  roles: [{ role: "read", db: dbName }]
});

// 3. Administrateur de la base : index, stats, gestion des utilisateurs
appDb.createUser({
  user: "healthcare_admin",
  pwd: process.env.HEALTHCARE_ADMIN_PASSWORD,
  roles: [
    { role: "dbAdmin", db: dbName },
    { role: "userAdmin", db: dbName }
  ]
});

print(`Utilisateurs créés sur la base ${dbName}`);
