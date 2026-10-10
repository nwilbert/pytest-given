# pytest-given — File Glossary Example

## ✓ A Guest booking an available room receives a Confirmation
`examples/file-glossary-booking/test_file_glossary_booking.py:60::test_book_available_room`

- **given** the «Room» is available
- **when** «Guest» «books» the «Room»
- **then** the «Guest» receives a «Confirmation»
- **then** the «Cancellation Policy» applies to the «Room»

## ✓ A Guest cannot book an unavailable room
`examples/file-glossary-booking/test_file_glossary_booking.py:77::test_book_unavailable_room`

- **given** no «Room» is available
- **when** «Guest» «books» a «Room»
- **then** no «Confirmation» is issued
