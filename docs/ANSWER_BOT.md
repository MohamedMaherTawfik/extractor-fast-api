# Answer Bot, Customer Service, and Auto-Send Engine

## Scope and safety posture

Answer Bot 1.0.0 is a local-first, API-first conversation engine. It normalizes inbound messages, resolves contacts and conversations, classifies intent, reads an allow-listed Product/Sales context, creates and validates a draft, and either queues a low-risk response or requests human review. It is not a source of truth for product, price, stock, order, delivery, balance, payment, promotion, or return data.

The default automation level is `LEVEL_2_LOW_RISK_AUTO`. Only supported, sufficiently confident intents with complete and fresh facts can be sent automatically. Complaints, payment and balance questions, returns, medical concerns, prompt-injection attempts, missing or ambiguous facts, and provider failures are held for review. Payment images are evidence only and never prove payment.

## Conversation flow

~~~text
Channel adapter -> normalized inbound Message -> contact/conversation resolution
    -> multilingual intent + validated entities -> read-only business context
    -> ResponsePlan -> deterministic local draft -> ResponseValidator
    -> approved outbound queue OR human handoff
    -> CRM signal / consent / follow-up state + audit events
~~~

Conversation memory is limited to recent messages, resolved entities, and pending actions. CRM signals are reviewable business observations; they never silently rewrite Customer or Lead source data. The engine does not infer sensitive personal traits.

## Channels and providers

`BaseMessagingChannel` defines receive, parse, send, media, read-state, delivery-state, contact-normalization, and thread-normalization operations. The registry exposes explicit availability for WhatsApp, Instagram DM, Facebook Messenger, website/app chat, email, Telegram, SMS, and call-center notes. This phase registers deterministic no-network mock and local website-chat adapters only. Real connectors remain `not_configured` and require separate credentials, webhook verification, permissions, and live integration tests.

`ConversationModelProvider` separates classify, entity extraction, generation, summarization, and tool-plan capabilities. The configured provider is deterministic and local. `LOCAL_ONLY` privacy mode rejects a provider that is not local. Prompt packages contain only recent targeted context and allow-listed business facts, not database dumps or secrets.

## Grounded business context

The context service uses Product/Sales repositories and services read-only. Product identification is exact against SKU, barcode, approved names, brand, and aliases. Orders and invoices require exact identifiers and customer ownership checks. Customer-specific approved pricebooks and quantity tiers take precedence; absent prices return review instead of an estimate. Stock comes from the inventory ledger/reservation context and is mapped to `IN_STOCK`, `LOW_STOCK`, or `OUT_OF_STOCK` only when a current record exists.

Approved knowledge is stored as immutable versions with lifecycle, effective dates, language, domain, keywords, and provenance. Retrieval returns only approved active versions. Responses persist the provider, prompt/rules versions, selected knowledge versions, business record snapshot, tools used, decision, validation findings, and audit events.

## Outbound controls and customer service

Outbound messages progress through `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `QUEUED`, `SENT`, `DELIVERED`, `READ`, `FAILED`, or `CANCELLED`. Idempotency keys, source message decisions, provider IDs, and outbound hashes prevent duplicate processing and sends. The queue uses configured bounded attempts and backoff; exhausted messages are dead-lettered and handed to a human queue.

Human handoffs record reason, priority, queue, related customer/order, and a concise factual summary. Internal notes and human edits are audited. Follow-ups enforce consent, do-not-contact state, quiet hours, cooldown, and maximum attempts. Marketing consent is separate from transactional communication.

Telesales tasks and CRM signals are reviewable drafts. Quote drafts use approved prices and expose approval requirements. Order drafts can advance only to `READY_FOR_SALES_REVIEW`; this engine never posts a Sales Order, Invoice, Payment, Inventory Movement, or Customer mutation.

## API surface

- Channel status, mock inbound ingestion, conversation list/detail/reply/assign/resolve/handoff
- Answer Bot process, dry-run draft, and validation
- Message approval, edit, send, cancel, delivery events, and outbound queue execution
- Follow-up create/list/cancel/run and contact consent
- Knowledge list/create/version update/search
- CRM signal list/review, telesales tasks, quote drafts, and order drafts/review confirmation

## Configuration and operations

`configs/answer_bot.yaml` owns automation, thresholds, freshness, provider/privacy mode, context limits, retries, quiet/business hours, SLAs, retention, channel availability, intent examples, escalation terms, forbidden claims, and queues. Secrets are not stored there. Production webhook connectors must verify signatures and use channel/provider secret stores. Tests use mock channels only and never send live messages.

The schema is Alembic revision `0009_answer_bot`. Run focused verification with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests\test_answer_bot.py -q
.\.venv\Scripts\python.exe -m alembic check
~~~

Known limitations: real messaging connectors are not configured; the deterministic classifier is phrase/config based; timezone execution uses the configured fixed UTC offset because Windows may not ship IANA timezone data; automatic attachment malware scanning and external AI providers require future adapters. Desktop UI and portable production runtime are outside this phase.
