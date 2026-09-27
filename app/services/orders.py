"""Order operations: placing, paying and cancelling purchases."""
from datetime import datetime
from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Book, Member, MemberTier, Order, OrderItem, OrderStatus
from app.services.members import ensure_can_access_restricted, get_member
from app.schemas import OrderCreate

# Percentage discount granted by each membership tier.
TIER_DISCOUNT_PERCENT: Dict[str, int] = {
    MemberTier.APPRENTICE.value: 0,
    MemberTier.ADEPT.value: 5,
    MemberTier.MASTER.value: 10,
    MemberTier.SUPREME.value: 15,
}

# Extra discount when the total quantity across all items reaches the threshold.
BULK_QUANTITY_THRESHOLD = 10
BULK_DISCOUNT_PERCENT = 5


def calculate_discount_percent(member: Member, total_quantity: int) -> int:
    """Tier discount, plus the bulk discount when total quantity >= threshold."""
    percent = TIER_DISCOUNT_PERCENT[member.tier]
    if total_quantity >= BULK_QUANTITY_THRESHOLD:
        percent += BULK_DISCOUNT_PERCENT
    return percent


def create_order(db: Session, data: OrderCreate, now: datetime) -> Order:
    """Place a pending order and reserve stock.

    Checks, in order (422 for empty items / bad quantity / duplicate books is done by the schema):
    1. 404 member not found; 404 any book not found
    2. 403 any book restricted and member tier below master
    3. 409 any book has insufficient stock (all-or-nothing: nothing is changed)
    Then stock is decremented for every item and prices are snapshotted.
    Pricing: discount_cents = subtotal * percent // 100; total = subtotal - discount.
    """
    # 1. Load member (404) and all books (404)
    member = get_member(db, data.member_id)
    books = []
    for item in data.items:
        book = db.get(Book, item.book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=f"Book {item.book_id} not found")
        books.append(book)

    # 2. Restricted check (403)
    for book in books:
        if book.restricted:
            ensure_can_access_restricted(member)

    # 3. Stock check — all-or-nothing (409)
    for book, item in zip(books, data.items):
        if book.stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for book {book.id}: requested {item.quantity}, available {book.stock}",
            )

    # 4. Decrement stock and snapshot prices
    order_items = []
    total_quantity = 0
    for book, item in zip(books, data.items):
        book.stock -= item.quantity
        total_quantity += item.quantity
        order_items.append(
            OrderItem(book_id=book.id, quantity=item.quantity, unit_price_cents=book.price_cents)
        )

    # 5. Pricing
    subtotal_cents = sum(oi.line_total_cents for oi in order_items)
    discount_percent = calculate_discount_percent(member, total_quantity)
    discount_cents = subtotal_cents * discount_percent // 100
    total_cents = subtotal_cents - discount_cents

    # 6. Persist
    order = Order(
        member_id=member.id,
        status=OrderStatus.PENDING.value,
        subtotal_cents=subtotal_cents,
        discount_percent=discount_percent,
        discount_cents=discount_cents,
        total_cents=total_cents,
        created_at=now,
        items=order_items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> Order:
    """Return an order by id, or raise 404."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def pay_order(db: Session, order_id: int) -> Order:
    """Mark a pending order as paid. 404 if missing; 409 if not pending."""
    order = get_order(db, order_id)
    if order.status != OrderStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Cannot pay an order that is {order.status}")
    order.status = OrderStatus.PAID.value
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order_id: int) -> Order:
    """Cancel a pending order and restore the reserved stock. 404 if missing; 409 if not pending."""
    order = get_order(db, order_id)
    if order.status != OrderStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Cannot cancel an order that is {order.status}")
    for item in order.items:
        book = db.get(Book, item.book_id)
        if book is not None:
            book.stock += item.quantity
    order.status = OrderStatus.CANCELLED.value
    db.commit()
    db.refresh(order)
    return order
