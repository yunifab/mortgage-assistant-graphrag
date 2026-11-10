# RDFox: how to start it (local prototype)

RDFox is the rule engine (Datalog reasoner) for the ontology + business rules.
The binary and licence are in `RDFox-win64-x86_64-7.5b/` (**not in git**: see `.gitignore`).

> Licence: academic licence, valid until 20 Mar 2027, used **for prototyping only** (agreed 2026-11-05).

## Start the server

Open a terminal **in the RDFox folder** (RDFox finds `RDFox.lic` in the current folder):

```powershell
cd C:\Users\20244647\Desktop\experimentation\FIBO\RDFox-win64-x86_64-7.5b
.\RDFox.exe -persistence off -server-directory "" -role admin -password admin daemon
```

You should see: `The RDFox endpoint is running on port 12110.` Leave the window open; `Ctrl+C` stops it.

If you get `Invalid mode 'admin'`, your PowerShell (Windows PowerShell 5.1) dropped the empty `""`. Add `--%` after
`.\RDFox.exe` so the arguments are passed as typed:
`.\RDFox.exe --% -persistence off -server-directory "" -role admin -password admin daemon`

What the options mean:
| Option | Meaning |
|---|---|
| `-persistence off` | everything stays in memory; a restart starts empty (fine: we reload from files) |
| `-server-directory ""` | no server folder needed (without this it fails with *"directory appears to be uninitialized"*) |
| `-role admin -password admin` | creates the login used by our code (local only) |
| `daemon` | run as a server with a REST endpoint on http://localhost:12110 |

The TLS warning at start-up is expected for a local prototype.

## Check that it works

```bash
curl -u admin:admin http://localhost:12110/datastores        # HTTP 200, list of datastores
```

Mini test of a rule (create store → facts → rule → query → delete):
```bash
B=http://localhost:12110; A="-s -u admin:admin"
curl $A -X POST "$B/datastores/smoketest"
curl $A -X POST -H "Content-Type: text/turtle" --data-raw '@prefix : <http://x/> . :son :age 17 . :father :age 45 .' "$B/datastores/smoketest/content"
curl $A -X POST -H "Content-Type: application/x.datalog" --data-raw '@prefix : <http://x/> . [?p, :violates, :R_MinAge] :- [?p, :age, ?a], FILTER(?a < 18) .' "$B/datastores/smoketest/content"
curl $A -H "Accept: text/csv" --data-urlencode "query=SELECT ?p ?r WHERE {?p <http://x/violates> ?r}" "$B/datastores/smoketest/sparql"
#   -> http://x/son,http://x/R_MinAge      (only the 17-year-old is flagged)
curl $A -X DELETE "$B/datastores/smoketest"
```

Tip: with curl, use `--data-raw` for Turtle/Datalog text. Plain `--data '@prefix…'` makes curl treat the
text after `@` as a file name.

## Settings for our code (`.env`)

```dotenv
RDFOX_ENDPOINT=http://localhost:12110
RDFOX_ROLE=admin
RDFOX_PASSWORD=admin
RDFOX_DATASTORE=mortgage
```
