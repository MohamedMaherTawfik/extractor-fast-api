# Sales Workbook Mapping

No CSV, XLS, or XLSX sales workbook was present in the project when the
Product/Sales Engine was implemented. Therefore no sheet was promoted to a
source of truth and no workbook-specific schema was invented.

The normalized intake contract is ready for later files:

| Workbook concept | Domain entity | Import behavior | Source of truth |
| --- | --- | --- | --- |
| Product/SKU list | Product Master candidate | Preview, validate unique SKU, require approval | Database after approved import |
| Retail/wholesale price list | PriceBook + lines | Version/effective-date validation, approval required | Database after approved import |
| Customer sheet | Customer Master candidate | Normalize, deduplicate, preserve optional lead reference | Database after approved import |
| Sales/invoice rows | Invoice staging | Preview, arithmetic/identity/dedup checks, approval, atomic post | Posted database invoice |
| Stock report | Inventory reconciliation staging | Compare to ledger; adjustment approval required | Inventory ledger |
| Payment report | Payment staging/allocation | Validate customer, method, amount, and allocation | Posted payment/allocation ledger |
| Purchase/supplier sheet | Purchase/AP candidates | Validate supplier/SKU and post through purchasing workflow | Database after posting |
| Dashboard/targets | Reporting or Sales Rep targets | Read as control/target only; never treated as actual sales | Transaction ledgers for actuals |

`POST /sales/import/preview` accepts CSV/XLSX, returns record/valid/invalid counts,
and performs no transactional write. A later real workbook can add a config-driven
column mapping without changing the normalized database model.
