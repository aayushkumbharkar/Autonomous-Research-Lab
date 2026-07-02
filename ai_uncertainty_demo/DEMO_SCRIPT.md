# DEMO_SCRIPT.md — Video Walkthrough Narration Guide

> **Total runtime: ~8 minutes**  
> **Format:** Timestamped talking points aligned to the demo steps in `run_ai_uncertainty_demo.sh`  
> **Target audience:** Engineering leads, DevOps teams, and anyone evaluating AI-assisted development workflows

---

## `[0:00–1:00]` — Introduction: What is Veritas?

**Visual:** Show the Veritas architecture diagram or the running frontend.

> "Welcome. Today we're going to demonstrate something critical for any team
> adopting AI coding assistants — how do you catch the mistakes that AI-generated
> code introduces before they reach production?"
>
> "First, let me introduce Veritas — the Autonomous Research Lab. It's a
> self-evaluating AI research platform built with FastAPI. It ingests interview
> transcripts, indexes them using hybrid semantic and keyword search, generates
> grounded answers with citations, verifies claims against source material, and
> continuously improves through a feedback loop."
>
> "The API surface includes endpoints for ingestion, hybrid search, research
> queries, evaluation, and interview management. Today we'll focus on the
> search endpoint — `/api/search` — which accepts a JSON body with a `query`
> field and returns ranked results with relevance scores."
>
> "The key question: if an AI coding agent writes a client for this API, how
> confident can we be that the generated code actually conforms to the real API
> contract?"

**Action:** Briefly show the OpenAPI contract in `specmatic.yaml` — scroll through
the `/api/search` endpoint definition highlighting the `query` field name,
the required `Content-Type`, and the endpoint path.

---

## `[1:00–1:30]` — The Problem: AI Uncertainty

**Visual:** Show `ai_generated_client.py` in the editor, highlighting the three bugs.

> "Here's what happened. We asked an AI coding agent to generate a Python
> client for the Veritas search API. It read partial documentation and
> produced this client. At first glance, it looks reasonable."
>
> "But there are three subtle bugs:"
>
> "Bug one — the field name. The AI used `query_text` instead of `query`.
> It's a plausible name, but it doesn't match the contract."
>
> "Bug two — the endpoint path. The AI guessed `/api/query` instead of
> `/api/search`. Again, reasonable inference, but wrong."
>
> "Bug three — the Content-Type. The AI used `requests.post(url, data=str(payload))`
> instead of `json=payload`, which means the request goes out as `text/plain`
> instead of `application/json`."
>
> "These are exactly the kind of mistakes AI makes — plausible but incorrect."

---

## `[1:30–3:00]` — Step 1: Unit Tests Pass (False Confidence)

**Visual:** Terminal running `python -m pytest test_ai_client_unit.py -v`

> "Now let's see what happens when we test this client the traditional way —
> with mock-based unit tests."

**Action:** Run `bash ai_uncertainty_demo/run_ai_uncertainty_demo.sh` and pause
after Step 1 output.

> "We have ten unit tests covering basic search, custom parameters, filters,
> weight configuration, empty results, and metadata. Every single test uses
> `unittest.mock.patch` to mock out `requests.post`."
>
> "And… they all pass. Ten out of ten. Green across the board."
>
> "This is the false confidence problem. The mocks faithfully reproduce
> whatever assumptions the developer — or the AI — baked into the test.
> The mock doesn't know the real endpoint is `/api/search`. It doesn't
> know the field should be `query`, not `query_text`. It just returns
> whatever canned response we told it to return."
>
> "If you're relying on mocks to validate AI-generated code, you're
> testing whether the AI is consistent with itself — not whether it's
> correct."

---

## `[3:00–4:30]` — Step 2: Specmatic Catches the Bugs

**Visual:** Terminal showing the Specmatic stub server starting, then the
flawed client's request being rejected.

> "Now let's bring in the contract. We're using Specmatic, which reads our
> OpenAPI specification in `specmatic.yaml` and spins up a stub server
> that enforces the contract exactly."
>
> "The stub server is starting in a Docker container. It knows every valid
> endpoint path, every required field name, every Content-Type the API
> accepts. If a request doesn't match the contract, it's rejected."

**Action:** Let the demo continue through Step 2.

> "Here's what happens when we run the flawed client against the stub."
>
> "The stub immediately rejects the request. Look at the error output —
> it tells us exactly what went wrong:"
>
> "First — the path `/api/query` doesn't match any endpoint in the contract.
> The stub has no route for it."
>
> "The stub's rejection log shows the contract violations clearly. This is
> not a vague 500 error — it's a precise, actionable diagnosis of what
> the client got wrong."
>
> "This is the power of contract testing. The stub doesn't care about our
> assumptions. It only cares about the specification."

---

## `[4:30–5:30]` — Step 3: The Diff

**Visual:** Terminal showing the formatted diff table.

> "Let's look at exactly what the AI got wrong, side by side with what
> the contract requires."

**Action:** Let Step 3 render the diff table.

> "Three bugs, three fixes:"
>
> "Endpoint: `/api/query` becomes `/api/search`."
>
> "Field name: `query_text` becomes `query`."
>
> "Content-Type: `text/plain` — from using `data=str(payload)` — becomes
> `application/json` by using `json=payload`."
>
> "Look at the code diff below the table. These are small, surgical changes.
> But without the contract test, we'd have shipped this broken client with
> full confidence, because our unit tests said everything was fine."

---

## `[5:30–6:30]` — Step 4: Fixed Client Passes

**Visual:** Terminal showing the fixed client getting a successful response
from the Specmatic stub.

> "Now let's run the corrected version — `search_fixed()` — against the
> same stub server."

**Action:** Let Step 4 complete.

> "The fixed client sends:"
>
> "A POST to `/api/search` — the correct endpoint."
>
> "A JSON body with `\"query\": \"What are the key findings?\"` — the correct
> field name."
>
> "With `Content-Type: application/json` — the correct header."
>
> "And the stub server responds with a valid, contract-compliant response.
> The request was accepted because it matched the specification exactly."
>
> "This is the complete lifecycle: flawed code fails the contract, we see
> exactly what's wrong, we fix it, and the fixed code passes."

---

## `[6:30–7:00]` — Summary

**Visual:** Terminal showing the final summary box from the script.

> "Let's recap what just happened:"
>
> "Step 1: Mock-based unit tests — all passed. False confidence."
>
> "Step 2: Specmatic contract test — rejected. Real bugs caught."
>
> "Step 3: Clear diff showing three specific violations."
>
> "Step 4: Fixed client — passed. Contract validated."
>
> "The contract acted as an objective source of truth that neither the AI
> nor the developer's assumptions could override."

---

## `[7:00–8:00]` — What This Means for AI-Assisted Development

**Visual:** Return to the editor or show a closing slide.

> "AI coding assistants are becoming a standard part of the development
> workflow. GitHub Copilot, Cursor, ChatGPT — they generate code faster
> than any developer can write it. But speed without correctness is
> dangerous."
>
> "The fundamental problem is that AI generates code based on probabilistic
> inference. It picks the most likely field name, the most plausible endpoint
> path. And when it's wrong, traditional testing methods — especially
> mock-based tests — can't catch it, because the mocks are built from the
> same flawed assumptions."
>
> "Contract testing changes the equation. The OpenAPI spec is the single
> source of truth. Specmatic turns that spec into an executable test
> oracle — a stub server that rejects anything that doesn't conform."
>
> "For teams adopting AI-assisted development, this is essential. It's not
> about slowing down — it's about having a safety net. Let the AI generate
> the first draft. Then run it against the contract. Fix what the contract
> catches. Ship with confidence."
>
> "This is what we've built into Veritas's CI pipeline — every push runs
> contract tests automatically. AI uncertainty becomes a solved problem,
> not an open risk."
>
> "Thank you for watching."

---

## Quick Reference — Demo Commands

```bash
# Run the full demo end-to-end
bash ai_uncertainty_demo/run_ai_uncertainty_demo.sh

# Run only the unit tests (Step 1)
cd ai_uncertainty_demo && python -m pytest test_ai_client_unit.py -v

# Start the stub server manually
docker run -d --name specmatic-stub-demo \
    -p 8000:8000 \
    -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml:ro" \
    specmatic/specmatic stub \
    --port 8000 "/usr/src/app/specmatic.yaml"

# Test flawed client manually
python ai_uncertainty_demo/ai_generated_client.py flawed http://localhost:8000

# Test fixed client manually
python ai_uncertainty_demo/ai_generated_client.py fixed http://localhost:8000

# Cleanup
docker stop specmatic-stub-demo && docker rm specmatic-stub-demo
```
