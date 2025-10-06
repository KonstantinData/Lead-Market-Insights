# Ablageübersicht für `log_storage/run_history`

Die folgende Übersicht dokumentiert, welche Komponenten die wichtigsten Dateien und Ordner im lokalen Laufprotokoll anlegen, welche Daten sie enthalten und wie sie in den Workflow eingebunden sind.

## `log_storage/run_history/agents/internal_research`
- **Verantwortliche Komponente:** `InternalResearchAgent` initialisiert bei Start sein Logverzeichnis unterhalb des globalen `AGENT_LOG_DIR` (Standard: `log_storage/run_history/agents`) und richtet einen dedizierten `internal_research.log`-Handler ein.【F:config/config.py†L251-L261】【F:config/config.py†L474-L483】【F:agents/internal_research_agent.py†L63-L88】【F:agents/internal_research_agent.py†L201-L215】
- **Inhalt & Datenstruktur:** Die Datei enthält zeilenweise Plaintext-Logeinträge im Format `timestamp level message`, die über den Python-Logger geschrieben werden.【F:agents/internal_research_agent.py†L201-L215】
- **Verwendungszweck im Workflow:** Die Agentenimplementierung schreibt operative Meldungen (z. B. Validierung, CRM-Abgleich, E-Mail-Ergebnisse) zur Laufzeit in dieses Log, um Support- und HITL-Teams Kontext zu geben.【F:agents/internal_research_agent.py†L102-L176】
- **Bezug zum Laufkontext:** Obwohl das Log nicht pro `run_id` partitioniert wird, enthalten parallele Workflow-Logs dieselben Schritte unter dem korrespondierenden `run_id`, wodurch Korrelation zur Run-Historie möglich ist.【F:agents/internal_research_agent.py†L613-L627】【F:logs/workflow_log_manager.py†L17-L59】

## `log_storage/run_history/research/artifacts/dossier_research`
- **Verantwortliche Komponente:** `DossierResearchAgent` legt pro Workflow-Run einen Unterordner `<run_id>` in diesem Artefakt-Root ab.【F:config/config.py†L251-L261】【F:config/config.py†L474-L483】【F:agents/dossier_research_agent.py†L48-L75】
- **Inhalt & Datenstruktur:** Pro Event wird eine JSON-Datei wie `<event_id>_company_detail_research.json` mit Feldern (`report_type`, `run_id`, `event_id`, `generated_at`, `company`, `summary`, `insights`, `sources`, `raw_input`) erzeugt.【F:agents/dossier_research_agent.py†L58-L205】
- **Verwendungszweck im Workflow:** Die resultierenden Artefakte werden an das Master-Resultat zurückgegeben (`artifact_path`) und später für CRM-Exports sowie PDF-Generierung genutzt.【F:agents/dossier_research_agent.py†L68-L155】【F:agents/workflow_orchestrator.py†L573-L637】
- **Bezug zum Laufkontext:** Ordner- und Dateinamen enthalten `run_id` und `event_id`, wodurch Artefakte eindeutig dem Workflow-Run zugeordnet sind.【F:agents/dossier_research_agent.py†L68-L205】

## `log_storage/run_history/research/artifacts/internal_research`
- **Verantwortliche Komponente:** `InternalResearchAgent` persistiert ergänzende JSON-Artefakte (z. B. `level1_samples.json`, `crm_matching_company.json`) unterhalb von `<run_id>`.【F:agents/internal_research_agent.py†L81-L155】【F:agents/internal_research_agent.py†L464-L493】
- **Inhalt & Datenstruktur:** Die Dateien enthalten Listen von Nachbarunternehmen bzw. CRM-Matching-Daten, die aus dem Trigger abgeleitet werden.【F:agents/internal_research_agent.py†L136-L195】【F:agents/internal_research_agent.py†L445-L493】
- **Verwendungszweck im Workflow:** Die Pfade werden im normalisierten Agentenergebnis zurückgegeben (`payload.artifacts`), sodass der Master-Workflow sie in Audit-Trails und CRM-Workflows referenzieren kann.【F:agents/internal_research_agent.py†L178-L195】
- **Bezug zum Laufkontext:** Unterordner nach `run_id` stellen sicher, dass mehrere Runs eines Unternehmens getrennt bleiben; Artefaktverweise tauchen im Run-Summary (`research`) wieder auf.【F:agents/internal_research_agent.py†L464-L472】【F:agents/workflow_orchestrator.py†L621-L635】

## `log_storage/run_history/research/artifacts/similar_companies_level1`
- **Verantwortliche Komponente:** `IntLvl1SimilarCompaniesAgent` erzeugt beim Persistieren der Ergebnisse einen Run-Unterordner (run_id oder Zeitstempel) unterhalb dieses Pfades.【F:config/config.py†L251-L261】【F:config/config.py†L474-L483】【F:agents/int_lvl_1_agent.py†L83-L158】
- **Inhalt & Datenstruktur:** Die JSON-Dateien (`similar_companies_level1_<event>.json`) enthalten Normalisate mit `company_name`, optionalem `run_id`/`event_id`, `generated_at` und einer `results`-Liste mit Matching-Details.【F:agents/int_lvl_1_agent.py†L117-L158】【F:agents/int_lvl_1_agent.py†L335-L358】
- **Verwendungszweck im Workflow:** Ergebnisse fließen in das `research`-Segment des Workflow-Outputs und dienen als Grundlage für PDF-Bundles und CRM-Dispatch.【F:agents/int_lvl_1_agent.py†L141-L156】【F:agents/workflow_orchestrator.py†L621-L635】【F:agents/workflow_orchestrator.py†L664-L675】
- **Bezug zum Laufkontext:** Bei fehlender `run_id` erzeugt der Agent Zeitstempel-Token, ansonsten wird der echte `run_id` verwendet; Dateien lassen sich daher direkt einem Run zuordnen.【F:agents/int_lvl_1_agent.py†L118-L156】【F:agents/int_lvl_1_agent.py†L335-L358】

## `log_storage/run_history/research/artifacts/workflow_runs`
- **Verantwortliche Komponente:** Der `WorkflowOrchestrator` legt für jeden Run `<run_id>/summary.json` an, sobald der Master-Workflow Ergebnisse liefert.【F:agents/workflow_orchestrator.py†L56-L609】
- **Inhalt & Datenstruktur:** `summary.json` ist eine Liste von Objekten mit `event_id`, `status`, `crm_dispatched`, Trigger-/Extraktionsdaten, eingebetteten `research`-Abschnitten und optionalen `pdf_artifacts`-Pfaden.【F:agents/workflow_orchestrator.py†L617-L637】
- **Verwendungszweck im Workflow:** Dient als Run-Manifest für Audits, PDF-Generierung und CRM-Nachverfolgung; fehlgeschlagene Generierungen werden geloggt.【F:agents/workflow_orchestrator.py†L573-L637】【F:agents/workflow_orchestrator.py†L637-L675】
- **Bezug zum Laufkontext:** Das Verzeichnis ist nach `run_id` segmentiert und bildet die Brücke zwischen Forschungsartefakten und `workflow_runs_total`-Metriken.【F:agents/workflow_orchestrator.py†L56-L609】【F:utils/observability.py†L692-L694】

## `log_storage/run_history/runs/state/negative_cache.json`
- **Verantwortliche Komponente:** `MasterWorkflowAgent` instanziiert einen `NegativeEventCache` unterhalb des Run-Log-Stammordners (`log_storage/run_history/runs/state`).【F:config/config.py†L251-L261】【F:agents/master_workflow_agent.py†L127-L136】
- **Inhalt & Datenstruktur:** Die JSON-Datei enthält ein `version`-Feld und ein `entries`-Mapping mit Event-IDs, Fingerprints, Entscheidungsstatus (`decision`), Zeitstempeln (`updated`, `last_seen`, `first_seen`) und `rule_hash`.【F:utils/negative_cache.py†L19-L205】
- **Verwendungszweck im Workflow:** Vor jedem Event entscheidet der Cache, ob unveränderte Ereignisse erneut verarbeitet werden müssen; nach Aktualisierungen wird der Cache auf die Platte geschrieben.【F:agents/master_workflow_agent.py†L234-L287】【F:utils/negative_cache.py†L104-L198】【F:agents/master_workflow_agent.py†L1247-L1250】
- **Bezug zum Laufkontext:** Der Cache lebt außerhalb einzelner Runs, speichert aber pro Event-ID Fingerprints, sodass Folge-Runs mit demselben `run_id` oder Ereignis den Verarbeitungspfad überspringen können.【F:agents/master_workflow_agent.py†L127-L287】【F:utils/negative_cache.py†L104-L251】

## `log_storage/run_history/runs/state/processed_events.json`
- **Verantwortliche Komponente:** `MasterWorkflowAgent` verwaltet zusätzlich einen `ProcessedEventCache`, der dieselbe State-Struktur nutzt.【F:agents/master_workflow_agent.py†L127-L137】
- **Inhalt & Datenstruktur:** Die Datei speichert unter `entries` pro Event-ID den SHA1-Fingerprint signifikanter Felder sowie den letzten `updated`-Zeitstempel.【F:utils/processed_event_cache.py†L18-L158】
- **Verwendungszweck im Workflow:** Nach erfolgreichem CRM-Dispatch markiert der Master-Agent das Event als verarbeitet; bei unverändertem Fingerprint wird das Event in künftigen Runs übersprungen.【F:agents/master_workflow_agent.py†L1177-L1218】【F:utils/processed_event_cache.py†L76-L138】
- **Bezug zum Laufkontext:** Der Cache ist Run-übergreifend, bezieht seine Schlüssel jedoch aus Event-IDs (die im Run-Summary auftauchen) und verhindert doppelte Arbeit innerhalb derselben oder späterer `workflow_runs`。【F:agents/workflow_orchestrator.py†L617-L637】【F:utils/processed_event_cache.py†L76-L158】

## `log_storage/run_history/runs/index.json`
- **Verantwortliche Komponente:** `LocalStorageAgent.record_run` pflegt ein Index-Array mit Metadaten zu jedem Run.【F:agents/local_storage_agent.py†L17-L106】【F:agents/master_workflow_agent.py†L1220-L1250】
- **Inhalt & Datenstruktur:** Jedes Listenelement enthält `run_id`, `log_path`, `recorded_at` sowie optionale Größen- und Audit-Informationen; Validierung erfolgt über das `RunsIndexEntry`-Schema.【F:agents/local_storage_agent.py†L65-L106】【F:utils/persistence.py†L21-L57】
- **Verwendungszweck im Workflow:** Das Indexfile bietet einen schnellen Lookup, wenn der Orchestrator oder Support vergangene Runs und deren Audit-Log-Pfade auffinden muss.【F:agents/local_storage_agent.py†L65-L107】【F:agents/master_workflow_agent.py†L1220-L1245】
- **Bezug zum Laufkontext:** Jeder Eintrag referenziert den physischen Logpfad und damit mittelbar das `run_id`-Verzeichnis unter `log_storage/run_history/runs/<run_id>` sowie dessen Audit-Log.【F:agents/local_storage_agent.py†L74-L106】【F:agents/master_workflow_agent.py†L1220-L1245】

## `log_storage/run_history/workflows`
- **Verantwortliche Komponente:** `WorkflowLogManager` verwaltet JSONL-Logs pro Run; Agents wie `InternalResearchAgent` verwenden ihn für schrittweise Workflow-Telemetrie.【F:config/config.py†L251-L259】【F:logs/workflow_log_manager.py†L17-L59】【F:agents/internal_research_agent.py†L63-L109】【F:agents/internal_research_agent.py†L613-L627】
- **Inhalt & Datenstruktur:** Pro Run entsteht eine Datei `<run_id>.jsonl`, deren Zeilen `timestamp`, `run_id`, `step`, `message`, optional `event_id` und `error` enthalten.【F:logs/workflow_log_manager.py†L30-L59】
- **Verwendungszweck im Workflow:** Dient als zentraler Audit-Trail für die Master- und Research-Agenten; Nachrichten werden bei jedem signifikanten Schritt geschrieben und können später zur Fehlersuche oder Compliance-Prüfung herangezogen werden.【F:agents/internal_research_agent.py†L102-L176】【F:logs/workflow_log_manager.py†L17-L59】
- **Bezug zum Laufkontext:** Dateinamen basieren auf dem `run_id`, wodurch alle Schritte eines Workflow-Durchlaufs in einer sequenziellen Logdatei gesammelt werden; diese wird beim Run-Finalisieren zusätzlich im Index referenziert.【F:logs/workflow_log_manager.py†L30-L59】【F:agents/master_workflow_agent.py†L1220-L1245】

