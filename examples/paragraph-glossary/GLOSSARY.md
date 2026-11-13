# Library Lending

How a lending library talks about loans, in the words its staff use.

## Language

### Lending

**Member**:
A person registered to borrow from the library.
_Avoid_: Patron, Customer

**Item**:
A single physical copy that a **Member** can borrow.
_Avoid_: Book (items include DVDs and games)

**Loan**:
The period in which a **Member** holds an **Item**.
_Avoid_: Checkout, Rental (in billing exports only)

**lend**:
Hand an **Item** to a **Member** as a **Loan**.

**Due Date**:
The day a **Loan** ends, after which a **Fine** accrues.

### Penalties

**Fine**:
A charge on a **Member** for keeping a **Loan** past its **Due Date**.
_Avoid_: Penalty, Late Fee

### Q&A

**Renewal**:
An extension of a **Loan**, which moves its **Due Date** later.

## Relationships

- A **Member** holds many **Loans**.
- A **Loan** covers exactly one **Item**.
- A **Loan** past its **Due Date** produces one **Fine**.

## Flagged ambiguities

- "Book" meant an **Item** in some conversations and the title in others.
