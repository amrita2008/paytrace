PayTrace
AI-Assisted Payment Reconciliation & Exception Investigation
<p align="center"> <strong>Turning financial reconciliation exceptions into actionable investigations.</strong> </p> <p align="center"> <a href="https://paytrace-jufchfg54-amrita24.vercel.app">🚀 Live Demo</a> &nbsp; • &nbsp; <a href="https://github.com/amrita2008/paytrace">📂 GitHub Repository</a> </p>
📌 Overview

PayTrace is an AI-assisted financial reconciliation platform designed to reduce the manual effort involved in investigating payment and settlement discrepancies.

Modern payment systems generate financial records across multiple systems such as payment gateways, settlement systems, and banks. Although these records represent the same underlying financial flow, they may not always align because of differences in transaction amounts, timestamps, statuses, identifiers, duplicate records, missing settlements, failed payments, or delayed settlements.

Traditional reconciliation systems are good at identifying that a discrepancy exists, but the difficult part often begins after the discrepancy is detected. An operator may still have to manually inspect payment records, settlement records, bank transactions, timestamps, amounts, transaction identifiers, and statuses to understand what actually happened.

PayTrace addresses this problem by combining a deterministic reconciliation engine with an AI-powered investigation layer.

The core idea is:

Deterministic systems establish financial truth. AI helps humans understand why an exception occurred.

AI is therefore not responsible for deciding whether a transaction is financially reconciled. Instead, it investigates exceptions that have already been identified by the deterministic reconciliation engine.

🎯 Problem Statement

A typical digital payment flow can be represented as:

Customer
   ↓
Payment Gateway
   ↓
Settlement System
   ↓
Bank

Each stage maintains its own records. For example, a payment gateway may record a successful payment, the settlement system may record when the amount was settled, and the bank may record the actual credit.

Ideally, these records should align. In real-world financial systems, discrepancies can occur frequently.

Common examples include:

Payment exists but settlement is missing
Payment and settlement amounts differ
Settlement occurs outside the expected timing window
Duplicate transactions appear
Payment is failed or refunded
Bank entry cannot be linked to a payment
Multiple possible records exist for the same transaction
Multiple settlement records need to be reconciled against a payment

The challenge is therefore not simply:

"Can we detect a mismatch?"

The larger operational question is:

"Why did this mismatch happen, what evidence supports the explanation, and what should the operator do next?"

Manual investigation of these exceptions is slow, repetitive, difficult to scale, and prone to human error.

💡 Proposed Solution — PayTrace

PayTrace separates financial reconciliation from exception investigation.

The complete workflow is:

Payment Gateway Data
        ↓
Settlement Data
        ↓
Bank Ledger Data
        ↓
Data Normalization
        ↓
Deterministic Reconciliation
        ↓
Financial Truth + Exceptions
        ↓
AI Investigation
        ↓
Evidence + Explanation
        ↓
Recommended Action
        ↓
Human Review

The deterministic engine establishes the financial outcome. The AI investigation layer then analyzes the already-established exception and provides a structured explanation.

This allows AI to add value without becoming the authority responsible for making financial decisions.

🧠 Core Design Principle: Deterministic First, AI Second

One of the most important architectural decisions in PayTrace was to avoid using an LLM for the actual financial reconciliation. Instead:

Financial Records
       ↓
Deterministic Reconciliation Engine
       ↓
Financial Truth + Exceptions
       ↓
AI Investigation Service
       ↓
Explanation + Evidence + Recommendation
       ↓
Human Decision

The deterministic reconciliation engine is the source of truth. The AI layer acts as an investigation assistant.

The AI does not:

Perform financial reconciliation
Override deterministic results
Assign transaction matches
Modify financial records
Access evaluation ground truth
Invent supporting evidence
Make the final financial decision
Expose chain-of-thought reasoning

This separation makes the system safer, more explainable, and easier to audit.

⚙️ System Approach
1. Data Normalization

PayTrace processes records from multiple financial sources:

Payment Gateway
Settlement Records
Bank Ledger

Because different systems can represent the same financial event differently, records are first normalized into a common internal representation. This creates a consistent foundation for reconciliation.

2. Deterministic Reconciliation

The reconciliation engine compares normalized records using deterministic rules. It identifies several types of reconciliation outcomes:

Exact Match — payment, settlement, and bank records align according to the defined reconciliation rules
Amount Mismatch — the expected and actual financial amounts differ
Timing Mismatch — related records exist but occur outside the expected timing relationship
Missing Settlement — a payment exists but no corresponding settlement can be established
Duplicate — multiple records appear to represent the same transaction
Failed / Refunded Payment — the payment status indicates it should not follow the normal successful settlement flow
Orphan Bank Entry — a bank entry exists without a corresponding payment flow
Ambiguous Match — multiple possible records prevent the system from establishing a deterministic match
🔍 Batch Reconciliation

Not every financial relationship is one-to-one. Some cases require multiple records to be considered together. PayTrace therefore supports grouped reconciliation and subset-based reconciliation with arithmetic verification.

For example:

Payment
   +
Settlement A
   +
Settlement B

may need to be considered as a group instead of independently. This allows the system to handle more complex financial relationships while maintaining deterministic reasoning.

🤖 AI Investigation Layer

Once the deterministic engine identifies an exception, the AI investigation service analyzes the relevant reconciliation context.

Instead of returning unrestricted natural-language output, the AI investigation follows a structured format:

Exception Type
      ↓
Summary
      ↓
Observed Facts
      ↓
Supporting Evidence
      ↓
Likely Explanation
      ↓
Unresolved Questions
      ↓
Recommended Action
      ↓
Confidence
      ↓
Human Review Required

For example, instead of displaying only:

AMOUNT_MISMATCH

PayTrace can provide an investigation containing:

Exception:
AMOUNT_MISMATCH

Observed Fact:
Payment amount differs from settlement amount.

Evidence:
Payment record
Settlement record

Likely Explanation:
The settlement amount does not correspond
to the original payment amount.

Recommended Action:
Review the settlement adjustment and verify
the source transaction.

Confidence:
0.xx

Human Review:
Required

The purpose of this output is to give an operator a useful starting point for investigation instead of forcing them to manually inspect every related record.

📚 Evidence-Based Investigation

The AI investigator works with structured reconciliation information and evidence identifiers. The investigation attempts to answer:

What happened?
      ↓
What evidence supports it?
      ↓
What is the likely explanation?
      ↓
What remains uncertain?
      ↓
What should the operator investigate next?

This keeps AI explanations connected to the financial records already identified by the reconciliation engine.

🛡️ AI Safety and Validation

LLMs can fail in several ways. They may:

Return malformed JSON
Return incomplete fields
Produce unsupported claims
Become unavailable
Return responses that do not satisfy the application's schema

PayTrace therefore validates AI responses before they are used by the application. The pipeline is:

AI Request
    ↓
LLM Response
    ↓
JSON Parsing
    ↓
Schema Validation
    ↓
  Valid?
   /   \
 Yes    No
  │      │
  ▼      ▼
 UI    Safe Fallback
          ↓
   Human Review

If the AI provider fails or produces invalid output, PayTrace does not fabricate an explanation. Instead, the system falls back to a human-review state.

This means: AI failure does not become financial misinformation.

🧩 AI Provider

PayTrace uses a local LLM architecture for its AI investigation layer:

Ollama
   ↓
Qwen3 1.7B

The local model approach was chosen to:

Avoid paid API dependencies
Keep the AI pipeline locally executable
Reduce dependency on external AI services
Maintain control over the investigation workflow
Provide a lightweight model suitable for the prototype

The provider is isolated behind an AI provider layer so that the underlying model can be replaced in the future without redesigning the complete application.

🏗️ Architecture
                         ┌────────────────────┐
                         │   React / Vite     │
                         │     Dashboard      │
                         └─────────┬──────────┘
                                   │
                                   │ REST API
                                   ▼
                         ┌────────────────────┐
                         │      FastAPI       │
                         │      Backend       │
                         └─────────┬──────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
                ▼                  ▼                  ▼
       ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐
       │ Reconciliation  │ │ Investigation   │ │     Data     │
       │     Engine      │ │     Service     │ │    Layer     │
       └────────┬────────┘ └────────┬────────┘ └──────────────┘
                │                   │
                │                   ▼
                │          ┌─────────────────┐
                │          │ Ollama / Qwen3  │
                │          │      1.7B       │
                │          └─────────────────┘
                │
                ▼
       ┌──────────────────┐
       │ Reconciliation   │
       │ Results &        │
       │ Exceptions       │
       └──────────────────┘
🔄 Complete Workflow
┌─────────────────────────┐
│ Payment Gateway Data    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Settlement Data         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Bank Ledger Data        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Data Normalization      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Deterministic           │
│ Reconciliation Engine   │
└────────────┬────────────┘
             │
       ┌─────┴─────┐
       ▼           ▼
   Matched      Exception
                   │
                   ▼
          ┌─────────────────┐
          │ AI Investigation│
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Evidence-based  │
          │ Explanation     │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Recommendation  │
          │ + Confidence    │
          └────────┬────────┘
                   │
                   ▼
             Human Review
📁 Project Structure
paytrace/
│
├── backend/
│   │
│   ├── ai/
│   │   ├── providers/
│   │   │   └── ollama_provider.py
│   │   │
│   │   └── investigation_service.py
│   │
│   ├── api/
│   │   ├── routes.py
│   │   ├── ai_routes.py
│   │   ├── ai_runner.py
│   │   └── reconciliation_runner.py
│   │
│   ├── reconciliation/
│   │   └── ...
│   │
│   ├── config.py
│   └── main.py
│
├── frontend/
│   │
│   ├── src/
│   │   ├── components/
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── data/
│   ├── payment_gateway.json
│   ├── settlements.json
│   └── bank_ledger.json
│
├── evaluation/
│   └── ...
│
├── tests/
│   └── ...
│
├── scripts/
│   └── ...
│
├── docs/
│   └── ...
│
├── requirements.txt
└── README.md
🖥️ Frontend

The PayTrace frontend is built using React, TypeScript, and Vite.

The dashboard provides a centralized interface for the reconciliation workflow, with visibility into:

Total reconciliation groups
Total payments
Total settlements
Total bank entries
Matched groups
Mismatched groups
Ambiguous groups
Duplicate groups
Human-review cases
Exception types

Users can open individual reconciliation groups to inspect the underlying financial records. For applicable exceptions, users can trigger an AI investigation and view:

Investigation summary
Exception type
Observed facts
Evidence
Likely explanation
Recommended action
Confidence
Human-review status
⚡ Backend

The backend is implemented using FastAPI. It provides REST APIs for:

Reconciliation summaries
Reconciliation results
Individual reconciliation groups
AI investigations

The backend follows a modular architecture:

API Layer
    ↓
Reconciliation Layer
    ↓
AI Investigation Layer
    ↓
Provider Layer

This makes individual components easier to test, maintain, and replace.

🔌 API Endpoints

Reconciliation Summary

GET /api/v1/reconciliation/summary

Returns: total groups, total payments, total settlements, total bank entries, status counts, exception counts, human-review count.

All Reconciliation Results

GET /api/v1/reconciliation/results

Returns reconciliation results for all groups.

Individual Reconciliation Group

GET /api/v1/reconciliation/results/{group_id}

Returns detailed information about a specific reconciliation group.

AI Investigation

GET /api/v1/reconciliation/results/{group_id}/investigate

Runs an AI investigation for an eligible reconciliation exception.

🛠️ Technology Stack
Layer	Tech
Backend	Python, FastAPI, Pydantic, Uvicorn
Frontend	React, TypeScript, Vite, CSS
AI	Ollama, Qwen3 1.7B, structured JSON generation, schema validation
Testing	Pytest
Deployment	Vercel (Frontend), Render (Backend)
Data	JSON-based payment gateway, settlement, and bank ledger records
📊 Evaluation

PayTrace includes an evaluation pipeline to measure the performance of the deterministic reconciliation engine.

The current evaluation dataset contains:

Metric	Result
Reconciliation Groups	42
Payments	55
Settlements	18
Bank Entries	22
Reconciliation Accuracy	94.4%
AI Pipeline Validation	30 / 30

The reconciliation evaluation and AI investigation layers are kept separate. The AI investigation system does not access the evaluation ground truth while generating explanations — this prevents the model from using known answers to generate its investigation output.

🧪 Testing

The project includes automated tests covering:

Domain models
Reconciliation logic
Exact matching
Exception detection
Batch reconciliation
Arithmetic verification
AI investigation
API behavior
Ollama provider
Provider error handling
Fallback behavior
Schema validation

Latest local test run: 181 tests passed AI pipeline validation: 30 / 30 structurally valid investigations

🚧 Problems Faced During Development
1. Defining the Role of AI

One of the biggest architectural challenges was determining where AI should actually be used. Using an LLM to perform the complete reconciliation process could result in hallucinated matches, inconsistent decisions, unsupported assumptions, and incorrect financial outcomes.

The solution was to clearly separate responsibilities:

Deterministic Engine → Financial Truth
AI                   → Investigation + Explanation

This became one of the core architectural principles of PayTrace.

2. Reliable Structured AI Output

LLMs naturally generate free-form text, while the application requires predictable structured data. The investigation pipeline therefore became:

LLM Response → JSON → Schema Validation → Application

Invalid responses are rejected instead of being blindly displayed.

3. Running an LLM Locally

Using a cloud LLM would introduce API costs and external dependencies. PayTrace instead uses Ollama running Qwen3 1.7B. Running a small local model introduced practical challenges around response reliability and structured output generation, so the provider layer was designed with strict validation and fallback handling.

4. Handling AI Provider Failures

During development, provider failures and malformed AI responses had to be handled safely. This resulted in JSON validation, schema validation, error categorization, safe fallback responses, and human-review escalation. The system never treats a failed AI response as a valid financial explanation.

5. Local vs Cloud Deployment

The local development environment can run Ollama and Qwen3 directly. However, a cloud backend cannot depend on a locally running model, which created a difference between local and cloud execution:

Local: FastAPI → Ollama → Qwen3 Cloud: FastAPI → AI Provider → Fallback if unavailable → Human Review

The architecture was designed so the core reconciliation system remains functional even when AI is unavailable.

6. Frontend and Backend Deployment

The frontend and backend were deployed separately — Vercel for the React frontend, Render for the FastAPI backend.

The frontend initially used relative API paths such as /api/v1/reconciliation/summary. When deployed to Vercel, these requests were interpreted as Vercel routes instead of requests to the Render backend, resulting in 404 Not Found. This highlighted the need for an API proxy/rewrite between the frontend deployment and backend deployment.

🔮 Improvements & Future Scope

PayTrace is currently a focused hackathon prototype. Several improvements could take it towards a production-grade financial reconciliation platform.

1. Database Integration The current prototype uses JSON-based records. A production implementation could use PostgreSQL or another transactional database, with entities like Payments, Settlements, Bank Entries, Reconciliation Results, Investigations, and Audit Logs — providing persistence, scalability, indexing, and more powerful querying.

2. Real-Time Reconciliation Instead of processing static datasets, PayTrace could consume financial events continuously via a message queue, enabling an event-driven architecture closer to real time:

Payment Event → Message Queue → Reconciliation Engine → Exception Detection → AI Investigation → Human Review

3. More Advanced Reconciliation Rules Future versions could support partial payments, split settlements, transaction fees, taxes, currency conversion, chargebacks, refunds, multiple settlement cycles, and configurable reconciliation rules.

4. Production-Scale Matching The deterministic matching engine could be extended with configurable multi-stage matching:

Exact Transaction ID → Amount + Date Match → Time-Window Match → Batch/Subset Match → Manual Review

The important principle would remain that the final financial outcome is deterministic and auditable.

5. Larger and Specialized AI Models The current system uses Qwen3 1.7B because it is lightweight and can run locally. For production workloads, a future model-routing architecture could send simple exceptions to a small/local model and complex exceptions to a larger specialized model — balancing cost, latency, accuracy, and model complexity.

6. Retrieval-Augmented Investigation A future version could retrieve similar historical reconciliation cases before generating an investigation, helping identify recurring operational patterns and previously resolved issues.

7. Human Feedback Loop Human investigators could approve, reject, or modify AI recommendations, feeding a feedback store that improves investigation quality over time.

8. Authentication and Authorization A production financial system would require user authentication, role-based access control, data access permissions, investigation history, audit trails, and secure API access.

9. Observability Production deployment could include structured logging, metrics, error tracking, AI latency monitoring, provider health monitoring, reconciliation performance metrics, and alerting.

🚀 Running Locally
Clone the Repository
bash
git clone https://github.com/amrita2008/paytrace.git
cd paytrace
Create Python Environment

Windows

bash
python -m venv .venv
.venv\Scripts\activate

macOS / Linux

bash
python3 -m venv .venv
source .venv/bin/activate
Install Backend Dependencies
bash
pip install -r requirements.txt
Start Backend

From the repository root:

bash
uvicorn backend.main:app --reload --port 8000

Backend: http://127.0.0.1:8000

🎨 Start Frontend

Open another terminal:

bash
cd frontend
npm install
npm run dev

Frontend: http://127.0.0.1:5173

🤖 Run AI Investigation Locally

Install Ollama and pull the model:

bash
ollama pull qwen3:1.7b

Start Ollama if required:

bash
ollama serve

PayTrace will then use Ollama → Qwen3 1.7B for local AI investigation.

🌐 Deployment
Frontend

The PayTrace frontend is deployed on Vercel.

Live Demo: 🚀 https://paytrace-jufchfg54-amrita24.vercel.app

Backend

The FastAPI backend is deployed on Render.

The production architecture is:

                   User
                    │
                    ▼
             ┌──────────────┐
             │    Vercel    │
             │ React/Vite   │
             └──────┬───────┘
                    │
                    │ REST API
                    ▼
             ┌──────────────┐
             │    Render    │
             │   FastAPI    │
             └──────┬───────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Reconciliation       AI Investigation
       Engine                Layer
                              │
                              ▼
                         Ollama/Qwen3
📌 Current Status

Completed

 Domain models
 Data normalization
 Deterministic reconciliation engine
 Exact matching
 Amount mismatch detection
 Timing mismatch detection
 Missing settlement detection
 Duplicate detection
 Failed/refunded detection
 Orphan bank entry detection
 Ambiguous match detection
 Batch reconciliation
 Arithmetic verification
 AI investigation service
 Ollama / Qwen3 provider
 Structured AI output
 Schema validation
 Safe AI fallback
 FastAPI integration
 React dashboard
 AI investigation UI
 Evaluation pipeline
 Automated testing
 Backend deployment
 Frontend deployment
🎯 Why PayTrace?

Traditional reconciliation primarily focuses on answering:

"Which transactions match?"

PayTrace goes one step further and asks:

"Why doesn't this transaction match, what evidence explains it, and what should the operator investigate next?"

Traditional workflow:

Detect Exception → Manual Investigation → Search Multiple Records → Understand Cause → Resolve

PayTrace:

Detect Exception → AI-Assisted Investigation → Evidence → Explanation → Recommended Action → Human Decision → Resolve

The goal is not to replace financial operators. The goal is to reduce the time they spend figuring out why an exception occurred and what should happen next.

🏆 Hackathon Context

PayTrace was built for the Razorpay AI Buildathon 2026.

The project explores how AI can be introduced into financial reconciliation while maintaining:

Deterministic financial correctness
Evidence-based investigation
Structured AI output
Safe failure behavior
Human oversight

The central idea behind PayTrace is:

Let deterministic systems establish financial truth. Let AI help humans understand why.

👩‍💻 Author

Amrita Vaish

Built for the Razorpay AI Buildathon 2026.

⭐ Final Takeaway
                    PAYTRACE
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      Deterministic             AI
      Reconciliation        Investigation
             │                   │
             ▼                   ▼
       Financial Truth       Explanation
             │                   │
             └─────────┬─────────┘
                       ▼
                 Human Decision

PayTrace combines deterministic financial reconciliation with AI-assisted exception investigation to make financial operations faster, safer, and easier to understand.
