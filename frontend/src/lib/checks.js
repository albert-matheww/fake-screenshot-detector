export const TYPE_STATUS_TEXT = {
  confident: "confident",
  tentative: "tentative",
  unknown: "could not be determined",
};

export const CHECK_STATUS_TEXT = {
  finding: "Found something",
  clear: "Found nothing",
  not_applicable: "Could not examine",
};

// The person can say what kind of screenshot it is; the type-specific checks then run on it.
export const SCREENSHOT_TYPES = [
  { value: "auto", label: "Not sure (detect automatically)" },
  { value: "payment_receipt", label: "Payment receipt or transfer" },
  { value: "bank_statement", label: "Bank statement or balance" },
  { value: "order_invoice", label: "Order, invoice or refund" },
  { value: "chat", label: "Chat conversation" },
  { value: "message_alert", label: "SMS, e-mail or notification" },
  { value: "social_post", label: "Social media post" },
  { value: "web_page", label: "Web page or dashboard" },
];

export const FIELD_KIND_LABELS = { refs: "Reference number", amounts: "Amount", dates: "Date", times: "Time" };
export const FIELD_STATUS_TEXT = {
  matched: "Matches",
  differs: "Differs",
  near: "Differs slightly: compare by eye",
  unclear: "Not found in the screenshot",
  not_in_source: "Not in the second source",
};
export const RECONCILE_STATUS_TEXT = {
  corroborated: "The second source agrees with the screenshot.",
  conflict: "The second source and the screenshot disagree.",
  review: "A reference or an amount differs slightly (one digit, or one extra leading digit). Compare it by eye.",
  partial: "Some facts match, but not enough to count as corroboration.",
  nothing_matched: "Nothing in the second source could be found in the screenshot.",
  no_facts: "The second source has no amount, date or reference to compare.",
};
