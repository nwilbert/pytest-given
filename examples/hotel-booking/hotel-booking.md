# pytest-given — Hotel Booking Example

## ✓ Carol picks a suite for the group
`examples/hotel-booking/test_hotel_booking.py:180::test_pick_suite`

- **given** our organizer «Carol»
- **given** the «Deluxe Suite» is listed as available
- **when** «Carol» searches for a «Room»
- **when** «Carol» selects the «Deluxe Suite»
- **then** the «Deluxe Suite» is held for the group

## ✓ Carol completes the booking for both guests
`examples/hotel-booking/test_hotel_booking.py:200::test_complete_booking`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has selected the «Deluxe Suite»
- **when** «Carol» adds «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» for the «Booking»
- **then** the «Booking System» «confirms» the «Booking»
- **then** the «Booking System» sends the «Confirmation» to «Alice» and «Bob»
- **when** «Alice» and «Bob» check in to the «Deluxe Suite»
- **then** both guests are checked in

## ✗ Payment is declined — the booking is not finalized · 4 cases
`examples/hotel-booking/test_hotel_booking.py:244::test_payment_declined` · error-handling, ticket/HB-17

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has added «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» by {payment_method} for the «Booking»
- **then** the «Booking System» «declines» the «Payment» because of {decline_reason}
- **then** the «Booking» stays pending and no «Confirmation» is sent to «Alice» or «Bob»

| payment_method | decline_reason | |
|---|---|---|
| credit card | insufficient funds | ✓ |
| debit card | expired card | ✓ |
| bank transfer | fraud check failed | ✓ |
| gift card | partial balance | ✗ |

- **gift card, partial balance** — failed:
  > assert 'unsupported payment method' == 'partial balance'
  > test_hotel_booking.py:283 in test_payment_declined

## ✓ Alice cancels her booking and is refunded
`examples/hotel-booking/test_hotel_booking.py:292::test_cancel_booking`

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» she paid for
- **when** «Alice» «cancels» the «Booking»
- **then** the «Booking System» «refunds» the «Payment» for the «Booking»
- **then** the «Booking System» sends a «Confirmation» to «Alice»

## ⊗ Alice rebooks her cancelled booking (planned feature) · expected failure
`examples/hotel-booking/test_hotel_booking.py:316::test_rebook_cancelled_booking` — expected to fail: rebooking is not implemented yet

- **given** our guest «Alice»
- **given** «Alice» has cancelled her stay
- **when** «Alice» «rebooks» the «Booking»

> rebooking a cancelled booking is not supported yet
> test_hotel_booking.py:313 in rebook_cancelled_booking

## ✓ Alice checks in, then cancels a later booking
`examples/hotel-booking/test_hotel_booking.py:344::test_check_in_then_cancel` · error-handling

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» now and one next month
- **when** «Alice» checks in to the «Deluxe Suite»
- **then** her current stay is checked in
- **when** «Alice» «cancels» her later «Booking»
- **then** the later booking is cancelled
- **when** she tries to cancel the stay she has checked in to
- **then** the cancellation is refused
