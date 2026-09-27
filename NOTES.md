# Sanctum Sanctorum - Submission Notes

*Note: I had my minor exams at IIIT Gwalior from September 20th to 26th, so I ended up tackling this entire assignment in a single, focused sitting today (September 27th), working from about 4:30 PM until submission (roughly 7 hours).*

**Live URL:** https://merkle.onrender.com/ (Swagger UI is at `/docs`)

## What I Finished
I was able to successfully complete all 5 steps of the assignment. The test suite is fully passing (`193/193`).

* **Books:** Implemented ISBN-13 checksum validation, stock management, partial updates (PATCH), and sorting/filtering.
* **Members:** Added member creation (handling 409s for duplicate emails) and built out `get_member_stats` to accurately report on orders, active/overdue loans, and late fees.
* **Orders:** Built out the pricing engine (combining tier discounts and bulk discounts), implemented strict checkout validations (checking for restricted access, existence, and stock limits), and managed the pending/paid/cancelled lifecycles with robust stock tracking.
* **Loans:** Implemented 14-day borrowing rules and tier-based limits. Added conflict checks (409) for members trying to borrow with overdue books or attempting to borrow a book they already have. Late fees (25c/day capped at book price) are calculated dynamically.
* **Reports:** Wrote the `top_books` endpoint using SQLAlchemy aggregations (`JOIN`, `GROUP BY`, `SUM`) to properly rank books based purely on `PAID` orders.

## Architectural Decisions & Trade-offs

1. **Dynamic Status & Fee Calculation vs. Stored State:** 
   Rather than using background cron jobs or database triggers to constantly update a loan's `status` (active/overdue) or `late_fee`, I decided to compute these dynamically at read-time inside the serialization layer (`to_loan_out`). This keeps the database logic drastically simpler, avoids race conditions, and eliminates the risk of stale state.

2. **Database Aggregations over Python Loops:** 
   For endpoints like `get_member_stats` and `top_books`, it's tempting to just fetch all the records and do the math in Python. Instead, I pushed the heavy lifting down to the PostgreSQL layer using SQLAlchemy's `func.sum` and `func.count`. This is significantly more memory-efficient and faster at scale.

3. **All-or-Nothing Stock Validation:** 
   When a member places an order, I explicitly loop through and validate stock for *all* requested items first, before deducting *any* stock. This guarantees we don't end up with a partially fulfilled cart (and messy rollbacks) if the final item in their cart triggers a 409 insufficient stock error.

## AI Usage
I used Antigravity IDE (with Claude Sonnet 4.6 Thinking and Gemini 3.1 Pro High) as a pairing partner throughout this sprint. 

* **How it helped:** It was incredibly useful for scaffolding boilerplate (like Pydantic schemas and FastAPI routes) and helping me rapidly write complex SQLAlchemy queries for the reports. We used a strict Test-Driven Development (TDD) approach—running the tests file-by-file and using the AI to help interpret tracebacks. For instance, it helped me quickly spot an off-by-one indexing bug in the tier ranking logic when a test failed.
* **Where it fell short:** At one point while building `get_member_stats`, the AI tried to fetch all loans and compute the statistics in Python. This completely broke the tests because it bypassed the test suite's frozen clock setup. I had to step in, override its approach, and rewrite it to use pure SQL scalar aggregations to guarantee accuracy and get the tests passing.
