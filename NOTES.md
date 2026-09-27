# Notes

**Live URL:** https://merkle.onrender.com/docs

## What was finished and what was not
I successfully completed all 5 steps of the assignment:
- **Step 1 (Books):** ISBN-13 checksum validation, stock management, partial updates, ordering/filtering.
- **Step 2 (Members):** Member creation (with 409 on duplicate emails), and `get_member_stats` reporting accurately on orders, loans, and late fees using direct database aggregations.
- **Step 3 (Orders):** Pricing rules (tier discounts, bulk discounts), checkout checks (403 restricted access, 404 existence, 409 stock), and order lifecycles (pending, paid, cancelled) with robust stock tracking.
- **Step 4 (Loans):** 14-day loan rules, enforcement of tier limits, 409 checks for overdue books or borrowing duplicates, and dynamic calculation of late fees (25c/day capped at book price) without storing mutable states in the DB.
- **Step 5 (Reports):** The `top_books` report uses advanced SQLAlchemy `JOIN`s, `GROUP BY`, and `SUM` to properly aggregate and order only `PAID` order items.

Every test in the provided test suite now passes (`193/193`).

## Architectural decisions & trade-offs
1. **Dynamic Status & Fee Calculation:** Instead of relying on cron jobs or triggers to update a loan's `status` or `late_fee`, I computed them dynamically at read-time in the serialization layer (`to_loan_out`). This keeps the database logic much simpler and less prone to race conditions or stale data.
2. **Aggregations in SQL, not Python:** For endpoints like `get_member_stats` and `top_books`, I delegated the heavy lifting to the database layer (PostgreSQL) using SQLAlchemy's `func.sum` and `func.count`. This is vastly more memory-efficient than loading all a member's objects into Python to do the math. 
3. **All-or-nothing stock checks:** When placing an order, I explicitly check the stock for *all* items in a loop before deducting *any* stock. This guarantees we don't end up with partially fulfilled stock deductions if the 3rd item in a cart throws a 409 error.

## AI Usage
I used an AI assistant (Google Gemini) throughout this assignment to speed up the implementation and act as a pairing partner:
- **Scaffolding & Syntax:** It helped rapidly generate boilerplate for Pydantic models, FastAPI routes, and complex SQLAlchemy aggregations (like the `top_books` grouping).
- **Test-Driven Debugging:** We took a rigorous TDD approach, running the test suite file-by-file and using the AI to interpret tracebacks and fix edge cases (such as realizing the `test_tier_at_least_apprentice_can_access_unrestricted` test required fixing an off-by-one bug in the Tier indexing logic).
- **Where the AI was unhelpful:** At one point during `get_member_stats`, the AI tried to fetch all loans and compute stats in Python, which broke due to the test suite's frozen clock and in-memory test setup. I had to step in and direct the AI to rely exclusively on SQL scalar aggregations to guarantee accuracy and bypass the `NotImplementedError` cascading failures. 
