# pytest-given — pytest-given

## ✓ Guest books an available room
`examples/file-glossary-booking/test_file_glossary_booking.py:52::test_book_available_room`

- **given** the «Room» is available
- **when** «Guest» «books» the «Room»
- **then** the «Guest» receives a «Confirmation»
- **then** the «Cancellation Policy» applies to the «Room»

## ✓ Guest cannot book an unavailable room
`examples/file-glossary-booking/test_file_glossary_booking.py:67::test_book_unavailable_room`

- **given** no «Room» is available
- **when** «Guest» «books» a «Room»
- **then** no «Confirmation» is issued
- **then** the «Cancellation Policy» does not apply
