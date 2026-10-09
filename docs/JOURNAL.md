# Journal de bord – Migration MongoDB

Les étapes, les difficultés rencontrées et les solutions trouvées, dans l'ordre chronologique.

---

## Étape 0 – Préparation
- Lecture des ressources : cours NoSQL, documentation MongoDB, PyMongo et Docker.
- **Choix de MongoDB dans Docker** plutôt qu'une installation locale classique. L'environnement est ainsi portable et reproductible, comme demandé par le client.

## Étape 1 – Conteneur MongoDB
- `docker-compose.yml` : image `mongo:8.0`, volume persistant `mongo_data`, port 27017.

| Difficulté | Cause | Solution |
|---|---|---|
| Mot de passe root écrit en clair dans le compose | Risque de fuite sur GitHub | Variables dans `.env` (ignoré par Git), `.env.example` versionné |
| `Authentication failed` après un changement de mot de passe | Le compte root n'est créé qu'à l'initialisation d'un volume vide | `docker compose down -v` puis `up -d` |
| `Authentication failed` malgré le bon mot de passe | Caractères spéciaux mal transmis par PowerShell | Mot de passe lu dans le conteneur (`bash -c '... "$VAR"'`) ; recommandation : mots de passe alphanumériques |
| Caractère `@` dans le mot de passe | Il casse l'URI `mongodb://user:pwd@host` | `urllib.parse.quote_plus()` dans `config.py` |

## Étape 2 – Authentification et rôles
- Script `mongo-init/01-create-users.js` : `migration_user` (readWrite), `analyst_user` (read), `healthcare_admin` (dbAdmin + userAdmin).
- Vérification : `db.getUsers()` liste les 3 comptes, en SCRAM-SHA-256.
- Test du moindre privilège : `analyst_user` reçoit `Unauthorized` sur un `insertOne`. ✅
- Difficulté : une commande `docker` tapée dans mongosh provoquait une `SyntaxError`. Il faut quitter mongosh (`exit`) avant de lancer une commande système.

## Étape 3 – Analyse du dataset
- 55 500 lignes, 15 colonnes, aucune valeur manquante.
- Anomalies relevées :
  - 534 doublons exacts ;
  - 5 500 lignes identiques sauf l'âge (doublons « bruités ») ;
  - casse aléatoire dans les noms ;
  - noms d'hôpitaux mal formés ;
  - 108 montants négatifs ;
  - dates au format texte.
- Constat : aucun identifiant patient, et les noms ne sont pas uniques.

## Étape 4 – Modélisation
- 1 collection `admissions`, avec 1 document par séjour et 4 sous-documents thématiques.
- Validateur `$jsonSchema` côté serveur pour garantir le typage.
- 5 index choisis d'après les requêtes métier (voir README §5).

## Étape 5 – Script de migration
- Pipeline : chargement → contrôle avant → nettoyage → transformation → collection validée → insertion par lots → index → contrôle après → rapport.
- **Résultat : 50 000 documents.** Le chiffre rond confirme que les 5 500 lignes retirées étaient des copies artificielles.
- **Décisions :**
  - les quasi-doublons sont supprimés (1ʳᵉ occurrence gardée) ;
  - les montants négatifs sont conservés et signalés. *À confirmer avec le client.*
- **Idempotence** : la collection est recréée à chaque exécution, ce qui évite les doublons en cas de relance.

## Étape 6 – Tests automatisés
- pytest : 26 tests, dont 3 d'intégration qui nécessitent le serveur.
- `mongomock` permet de tester la logique sans serveur. Les tests d'intégration vérifient en plus que le validateur rejette les mauvais types.
- Difficulté : `mongomock` ne gère pas les validateurs `$jsonSchema`. Le paramètre `use_validator` est désactivé dans les tests unitaires, et le validateur est testé sur le vrai serveur.
- Difficulté : sans mot de passe défini, `MongoClient` lève une erreur avant même le ping. La création du client a été placée dans le bloc `try`, et les tests d'intégration sont ignorés proprement.

## Étape 7 – Conteneurisation du script
- `Dockerfile` (python:3.12-slim, utilisateur non root).
- Service `migration` dans le compose, avec `depends_on: condition: service_healthy` pour attendre que MongoDB réponde avant de migrer.

## Questions ouvertes pour Boris / le client
1. Les doublons qui ne diffèrent que par l'âge sont-ils bien des erreurs ?
2. Les montants négatifs sont-ils des remboursements ?
3. Existe-t-il un identifiant patient dans le système source ?
