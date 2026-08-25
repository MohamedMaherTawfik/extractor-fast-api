import asyncio

import httpx
import pytest
from sqlalchemy import delete

from backend.core.paths import paths
from backend.db.models.content_item import ContentItem
from backend.db.models.analysis import AnalysisRun
from backend.db.models.collection_run import CollectionRun
from backend.db.models.creator import Creator
from backend.db.models.import_batch import CreatorImportBatch, CreatorImportError
from backend.db.models.platform_account import PlatformAccount
from backend.db.models.pattern_recipe import (
    ContentDNA,
    Pattern,
    PatternMiningRun,
    PerformanceSnapshot,
    Recipe,
)
from backend.db.models.rules import (
    GenerationContract, GenerationContractVersion, HumanReviewRequest, MasterControl,
    Rule, RuleAuditLog, RuleDependency, RuleEvaluationResult, RuleEvaluationRun,
    RuleImportRun, RuleOverride, RuleSet, RuleSetMember, RuleVersion,
)
from backend.db.models.generation import (
    AssetReference, AssetVersion, ContinuityState, GeneratedAsset, GenerationAttempt,
    GenerationCostRecord, GenerationEvent, GenerationJob, GenerationQARun,
    GenerationQAResult, ModelProfile, PromptPackage, PromptPackageVersion,
    ProviderProfile, ProvenanceRecord, Storyboard, StoryboardShot,
)
from backend.db.models.sales import (
    AccountingJournal, AccountingJournalLine, ApprovalRequest, AuditLedger,
    BusinessEvent, CollectionActivity, Customer, DailyClose, Delivery,
    GoodsReceipt, GoodsReceiptLine, InventoryMovement, InventoryReservation,
    MscIntakeBatch, MscIntakeFile, MscInvoiceStaging, Payment,
    PaymentAllocation, PriceBook, PriceBookLine, Product, ProductBatch,
    ProductVersion, PurchaseOrder, PurchaseOrderLine, SalesInvoice,
    SalesInvoiceLine, SalesOrder, SalesOrderLine, SalesRep, SalesReturn,
    SalesReturnLine, Stocktake, StocktakeLine, Supplier, SupplierInvoice,
    SupplierPayment, Territory, Warehouse,
)
from backend.db.models.answer_bot import (
    AgentNote, BotDecision, ChannelAccount, Contact, Conversation,
    ConversationEvent, ConversationState, ConversationSummary, CRMSignal,
    EntityExtraction, FollowUp, HandoffRequest, IntentResult, KnowledgeItem,
    KnowledgeVersion, MarketingConsent, Message, MessageAttachment,
    MessageDeliveryEvent, MessageEdit, OrderDraft, QuoteDraft, ResponsePlan,
    ResponseTemplate, TelesalesTask, TemplateVersion, WebhookEvent,
)
from backend.db.models.leads import (
    Lead, LeadControlImport, LeadDedupeEvent, LeadJob, LeadRun, LeadSource,
    LeadSourceRecord, OptInLead,
)
from backend.db.session import init_database, session_scope
from backend.main import app


def clear_domain_data() -> None:
    with session_scope() as session:
        for model in (LeadDedupeEvent, LeadSourceRecord, LeadJob, LeadRun, Lead, LeadControlImport, OptInLead, LeadSource):
            session.execute(delete(model))
        for model in (
            MessageDeliveryEvent, MessageEdit, BotDecision, ResponsePlan,
            EntityExtraction, IntentResult, MessageAttachment,
            ConversationSummary, ConversationEvent, AgentNote, FollowUp,
            MarketingConsent, CRMSignal, HandoffRequest, TelesalesTask,
            QuoteDraft, OrderDraft, ConversationState, Message, Conversation,
            Contact, KnowledgeVersion, KnowledgeItem, TemplateVersion,
            ResponseTemplate, ChannelAccount, WebhookEvent,
        ):
            session.execute(delete(model))
        for model in (
            AuditLedger, BusinessEvent, ApprovalRequest, AccountingJournalLine,
            AccountingJournal, MscInvoiceStaging, MscIntakeFile, MscIntakeBatch,
            DailyClose, Delivery, SalesReturnLine, SalesReturn,
            SupplierPayment, SupplierInvoice, GoodsReceiptLine, GoodsReceipt,
            PurchaseOrderLine, PurchaseOrder, CollectionActivity,
            PaymentAllocation, Payment, InventoryReservation,
            InventoryMovement, SalesInvoiceLine, SalesInvoice, SalesOrderLine,
            SalesOrder, StocktakeLine, Stocktake, ProductBatch, PriceBookLine,
            ProductVersion, Product, Customer, PriceBook, Warehouse, SalesRep,
            Territory, Supplier,
        ):
            session.execute(delete(model))
        session.execute(delete(ProvenanceRecord))
        session.execute(delete(StoryboardShot))
        session.execute(delete(Storyboard))
        session.execute(delete(ContinuityState))
        session.execute(delete(GenerationCostRecord))
        session.execute(delete(GenerationQAResult))
        session.execute(delete(GenerationQARun))
        session.execute(delete(AssetReference))
        session.execute(delete(AssetVersion))
        session.execute(delete(GeneratedAsset))
        session.execute(delete(PromptPackageVersion))
        session.execute(delete(PromptPackage))
        session.execute(delete(GenerationEvent))
        session.execute(delete(GenerationAttempt))
        session.execute(delete(GenerationJob))
        session.execute(delete(ModelProfile))
        session.execute(delete(ProviderProfile))
        session.execute(delete(GenerationContractVersion))
        session.execute(delete(GenerationContract))
        session.execute(delete(HumanReviewRequest))
        session.execute(delete(RuleEvaluationResult))
        session.execute(delete(RuleEvaluationRun))
        session.execute(delete(RuleAuditLog))
        session.execute(delete(RuleOverride))
        session.execute(delete(MasterControl))
        session.execute(delete(RuleImportRun))
        session.execute(delete(RuleSetMember))
        session.execute(delete(RuleSet))
        session.execute(delete(RuleDependency))
        session.execute(delete(RuleVersion))
        session.execute(delete(Rule))
        session.execute(delete(Recipe))
        session.execute(delete(Pattern))
        session.execute(delete(PatternMiningRun))
        session.execute(delete(PerformanceSnapshot))
        session.execute(delete(ContentDNA))
        session.execute(delete(AnalysisRun))
        session.execute(delete(CollectionRun))
        session.execute(delete(ContentItem))
        session.execute(delete(CreatorImportError))
        session.execute(delete(PlatformAccount))
        session.execute(delete(CreatorImportBatch))
        session.execute(delete(Creator))


@pytest.fixture(autouse=True)
def isolated_domain_data():
    init_database()
    paths.ensure_runtime_directories()
    existing_imports = set(paths.imports.rglob("*"))
    existing_raw_files = set(paths.raw.rglob("*"))
    existing_media_files = set(paths.media.rglob("*"))
    existing_generated_files = set(paths.generated_assets.rglob("*"))
    existing_provider_responses = set(paths.provider_responses.rglob("*"))
    existing_lead_files = set(paths.lead_acquisition.rglob("*"))
    existing_lead_control_files = set(paths.lead_control_imports.rglob("*"))
    clear_domain_data()
    yield
    clear_domain_data()
    for base, existing in (
        (paths.imports, existing_imports),
        (paths.raw, existing_raw_files),
        (paths.media, existing_media_files),
        (paths.generated_assets, existing_generated_files),
        (paths.provider_responses, existing_provider_responses),
        (paths.lead_acquisition, existing_lead_files),
        (paths.lead_control_imports, existing_lead_control_files),
    ):
        for created_path in sorted(
            set(base.rglob("*")) - existing,
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            if created_path.is_file():
                created_path.unlink()
            elif created_path.is_dir() and not any(created_path.iterdir()):
                created_path.rmdir()


@pytest.fixture
def api_request():
    def request(method: str, url: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    return request
