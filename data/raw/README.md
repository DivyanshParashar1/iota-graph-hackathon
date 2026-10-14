# DataCo Smart Supply Chain (raw)

* `DataCoSupplyChainDataset.csv.gz`: 180,519 rows x 53 columns, **latin-1 encoded**. Read with
  `pd.read_csv(path, encoding="latin-1")`. The uncompressed CSV is gitignored.
* `DescriptionDataCoSupplyChain.csv`: data dictionary.
* sha256 of the uncompressed CSV: `fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6`

Source: Constante, Fabian; Silva, Fernando; Pereira, António (2019), "DataCo SMART SUPPLY CHAIN FOR BIG DATA
ANALYSIS", Mendeley Data, V1, doi: 10.17632/8gx2fvg2k6.1. License: CC BY 4.0.
Downloaded from https://data.mendeley.com/datasets/8gx2fvg2k6/1 on 2026-10-15.

## Profile (measured)

| Fact | Value |
|---|---|
| Order dates | 2015-01-01 to 2018-01-31 |
| Orders / order items | 65,752 / 180,519 (1 to 5 items per order, median 3) |
| Products / categories / departments | 118 / 50 / 11 |
| Customers | 20,652 |
| Markets | LATAM 51,594; Europe 50,252; Pacific Asia 41,260; USCA 25,799; Africa 11,614 (item rows) |
| Order regions | 23 (some values carry trailing spaces, e.g. `"West of USA "`: strip them) |
| Order Status | COMPLETE, PENDING_PAYMENT, PROCESSING, PENDING, CLOSED, ON_HOLD, SUSPECTED_FRAUD, CANCELED, PAYMENT_REVIEW |
| Open statuses (used for "at risk") | PENDING, PROCESSING, PENDING_PAYMENT, ON_HOLD, PAYMENT_REVIEW → 33,932 orders, 93,658 items, $19.1M sales |
| Shipping Mode | Standard Class, Second Class, First Class, Same Day |
| Late rate by mode | First 0.953, Second 0.766, Same Day 0.457, Standard 0.381 |
| PII columns to drop | Customer Email, Customer Fname, Customer Lname, Customer Password, Customer Street, Customer Zipcode, Order Zipcode, Latitude, Longitude, Product Image, Product Description |
