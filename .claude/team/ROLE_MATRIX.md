# Role Ownership Matrix

| Decision or work | Accountable role | Common contributors |
|---|---|---|
| Product problem, scope, priority, acceptance criteria | Product Manager | Researcher, Business Analyst, stakeholders |
| External product/workflow evidence | Product Researcher | Product Manager, Designer |
| Business rules, processes, permissions, data definitions | Business Analyst | Product Manager, Architect |
| ClickUp structure, sequencing, status, dependencies, milestones | Delivery Manager | Product Manager, all specialists |
| Architecture, APIs, data model, integrations, NFR trade-offs | Software Architect | Engineers, Security, DevOps |
| User flow, interaction, visual states, accessibility | UI/UX Designer | Product, Research, Engineers |
| Web implementation | Frontend Engineer | Design, Backend, QA |
| Server/data implementation | Backend Engineer | Architect, Security, QA |
| Mobile implementation | Mobile Engineer | Design, Backend, QA |
| AI behaviour, evaluation, safety, model operations | AI Engineer | Product, Security, Backend, QA |
| CI/CD, infrastructure, observability, deployment, rollback | DevOps Engineer | Backend, Security, QA |
| Independent code findings | Code Reviewer | Implementing engineers |
| Security/privacy verdict | Security Reviewer | Architect, Engineers, DevOps |
| Verification and release test evidence | QA Engineer | All implementation roles |
| User/developer/operations/release documentation | Documentation Writer | Product, Engineers, DevOps, QA |
| Cross-stage coordination and gate enforcement | `/build` | Delivery Manager and every required specialist |

A role may contribute outside its accountable area but cannot silently approve another role's decision.
