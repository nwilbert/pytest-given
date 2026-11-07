# Paragraph Glossary Example

## ✓ A Member borrows an Item for a Loan
`examples/paragraph-glossary/test_paragraph_glossary.py::test_lend_an_item`

- **given** a «Member» and an «Item»
- **when** the library «lends» the «Item»
- **then** the «Loan» ends on its «Due Date»

## ✓ A Renewal moves the Due Date later
`examples/paragraph-glossary/test_paragraph_glossary.py::test_renewal`

- **given** a «Loan» of an «Item»
- **when** the «Member» asks for a «Renewal»
- **then** the «Due Date» moves three weeks later

## ✓ A late return costs a Fine
`examples/paragraph-glossary/test_paragraph_glossary.py::test_fine_for_late_return`

- **given** a «Loan» that is past its «Due Date»
- **when** the «Member» returns the «Item» four days late
- **then** the «Member» owes a «Fine»

## ✓ A timely return costs no Fine
`examples/paragraph-glossary/test_paragraph_glossary.py::test_no_fine_for_timely_return`

- **given** a «Loan» that is not yet past its «Due Date»
- **when** the «Member» returns the «Item»
- **then** the «Member» owes no «Fine»
