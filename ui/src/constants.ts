// Mirrors ripple/onboarding/models.py. The UI only needs the lists it offers as choices; the server is the
// authority and rejects anything else.

export const PROPERTY_TYPES = [
  "string",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "currency",
  "percent",
  "geo",
  "id",
  "enum",
  "list",
] as const;

export const CARDINALITIES = ["one-to-one", "one-to-many", "many-to-one", "many-to-many"] as const;
