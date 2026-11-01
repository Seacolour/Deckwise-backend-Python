# Database migration source

`migration/V1__foundation.sql` through `V12__openrouter_model_credentials.sql` are byte-for-byte copies from `D:/Code/AgentWorkbench/backend/src/main/resources/db/migration` as of this project setup. They create the `backend_data` schema in a separate local database. The Python service will initially use only the tables required by the Web and Agent paths.

`V13__email_login.sql` is Python-owned. It adds PostgreSQL storage for email codes and Web sessions, replacing the Java backend's Redis-backed login state.

Do not edit applied Flyway migrations. Once the Python feature set is stable, remove unused tables with forward migrations and build a separate clean baseline for fresh installations if needed.
