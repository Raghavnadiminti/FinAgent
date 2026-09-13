# AI Accountant — Agentic Accounting System

An agentic AI accounting platform built with **Google ADK + MCP + PostgreSQL**, designed for accounting analytics, reconciliation, validation, conversational assistance, exception investigation, and controlled accounting actions.

## Architecture

```text
                         USER
                           |
                           v
                    +--------------+
                    | ORCHESTRATOR |
                    +------+-------+
                           |
                    COMMON MEMORY
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
     ANALYTICS       RECONCILIATION     VALIDATION
       AGENT              AGENT            AGENT
          |                |                |
          +----------------+----------------+
                           |
                           v
                    COMMON MCP SERVER
                           |
                    +------+------+
                    |             |
                    v             v
                PostgreSQL     MongoDB
```

### Core principles

- **PostgreSQL = accounting source of truth**
- **MCP = controlled tool/data interface**
- **Specialist agents = reasoning and tool selection**
- **Orchestrator = routing and workflow coordination**
- **Memory = conversational/workflow context, not financial truth**
