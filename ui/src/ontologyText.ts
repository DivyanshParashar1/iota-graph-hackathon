import type { OntologySpec, RelationshipSpec, TypeSpec } from "./api";

// The ontology in plain English, built from the spec alone (no model call): every link type becomes a sentence
// that says who does what to whom and how many, so someone who has never seen a graph can read the model.

/** "SHIPS_TO" -> "ships to"; "PART_OF" -> "is part of"; "BASED_IN" -> "is based in". */
export function verb(type: string): string {
  const words = type.toLowerCase().split(/[_\s]+/).filter(Boolean);
  const phrase = words.join(" ");
  const passive = /^(part|located|based|sited|contained|used|made|owned|managed|stored|assigned|destined|carried|contracted|served|supplied|operated|linked|related|connected|member|subject|derived)\b/;
  if (passive.test(words[0] ?? "") && !/^(serves|supplies)/.test(phrase)) return `is ${phrase}`;
  return phrase;
}

/** "Category" -> "Categories", "Shipment" -> "Shipments". Labels are CamelCase; split for reading. */
export function human(label: string): string {
  return label.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
}

export function plural(label: string): string {
  const h = human(label);
  if (/[^aeiou]y$/i.test(h)) return `${h.slice(0, -1)}ies`;
  if (/(s|x|z|ch|sh)$/i.test(h)) return `${h}es`;
  return `${h}s`;
}

export const CARD_SHORT: Record<string, string> = {
  "one-to-one": "1:1",
  "one-to-many": "1:N",
  "many-to-one": "N:1",
  "many-to-many": "N:M",
};

export const CARD_LABEL: Record<string, string> = {
  "one-to-one": "One to one",
  "one-to-many": "One to many",
  "many-to-one": "Many to one",
  "many-to-many": "Many to many",
};

export interface Sentence {
  rel: RelationshipSpec;
  /** Segments: plain text, or a type reference to render as a link. */
  parts: ({ text: string } | { type: string; text: string })[];
}

/** One link type as a sentence: "Each Supplier supplies many Raw Materials; a Raw Material can come from many Suppliers." */
export function sentence(r: RelationshipSpec): Sentence {
  const v = verb(r.type);
  const from = r.from;
  const to = r.to;
  const self = from === to;
  const P: Sentence["parts"] = [];
  const t = (text: string) => P.push({ text });
  const ty = (type: string, text: string) => P.push({ type, text });
  switch (r.cardinality) {
    case "one-to-one":
      t("Each "); ty(from, human(from)); t(` ${v} exactly one `); ty(to, self ? `other ${human(to)}` : human(to));
      t(", and each "); ty(to, human(to)); t(" has one "); ty(from, human(from)); t(".");
      break;
    case "one-to-many":
      t("Each "); ty(from, human(from)); t(` ${v} many `); ty(to, plural(to));
      t("; each "); ty(to, human(to)); t(" belongs to exactly one "); ty(from, human(from)); t(".");
      break;
    case "many-to-one":
      t("Each "); ty(from, human(from)); t(` ${v} one `); ty(to, human(to));
      t("; a "); ty(to, human(to)); t(" can have many "); ty(from, plural(from)); t(".");
      break;
    default:
      if (self) {
        t("A "); ty(from, human(from)); t(` ${v} other `); ty(to, plural(to)); t(", in any combination.");
      } else {
        t("A "); ty(from, human(from)); t(` ${v} many `); ty(to, plural(to));
        t(", and a "); ty(to, human(to)); t(" can be linked to many "); ty(from, plural(from)); t(".");
      }
  }
  return { rel: r, parts: P };
}

export function sentenceText(r: RelationshipSpec): string {
  return sentence(r).parts.map((p) => p.text).join("");
}

export interface TypeStory {
  type: TypeSpec;
  outgoing: Sentence[];
  incoming: RelationshipSpec[];
}

/** The model as a reading order: the types in the order the ontology agent wrote them (it lists them roughly
 *  upstream to downstream), each with the sentences for its outgoing links. */
export function story(spec: OntologySpec): TypeStory[] {
  return spec.types.map((type) => ({
    type,
    outgoing: spec.relationships.filter((r) => r.from === type.label).map(sentence),
    incoming: spec.relationships.filter((r) => r.to === type.label && r.from !== type.label),
  }));
}
