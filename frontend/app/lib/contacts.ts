/** Studio contacts and seller requisites — the storefront's single source for both. */

export interface Contacts {
  city: string;
  street: string;
  address: string;
  phone: string;
  phoneDisplay: string;
  email: string;
  hours: string;
  telegram: string;
  whatsapp: string;
  vk: string;
  maxLink: string;
  mapEmbed: string;
}

export const SITE_NAME = "Memiro";

const CITY = "Санкт-Петербург";
const STREET = "Александра Матросова, 4к2ж";

export const CONTACTS: Contacts = {
  city: CITY,
  street: STREET,
  address: `${CITY}, ${STREET}`,
  phone: "+79812304050",
  phoneDisplay: "+7 981 230-40-50",
  email: "memiro.ru@yandex.ru",
  hours: "Ежедневно, по предварительной записи",
  telegram: "https://t.me/memiro_shop",
  whatsapp: "https://wa.me/79812304050",
  vk: "https://vk.com/memirospb",
  // The owner has no MAX profile yet; an empty link draws no icon.
  maxLink: "",
  mapEmbed: "https://yandex.ru/map-widget/v1/?um=constructor%3A0d49dffecadc7ce7a218e08a0b62b35502b15e05faa72ecea01c3be9dea4a3f1&source=constructor",
};

export interface Requisite {
  label: string;
  value: string;
}

// Distance-selling rules require the seller to be named on the storefront
// (п. 18 ПП РФ 2463). An empty value is not printed: a wrong OGRN is worse
// than a missing one, and the owner fills these before the site goes live.
const SELLER = {
  name: "",
  ogrn: "",
  inn: "",
  address: "",
};

export const SELLER_REQUISITES: Requisite[] = [
  { label: "", value: SELLER.name },
  { label: "ОГРН/ОГРНИП", value: SELLER.ogrn },
  { label: "ИНН", value: SELLER.inn },
  { label: "Адрес", value: SELLER.address },
].filter((requisite) => requisite.value !== "");

/** Links to the studio outside the site, in the order the storefront prints them. */
export const SOCIAL_LINKS: { href: string; label: string }[] = [
  { href: CONTACTS.maxLink, label: "MAX" },
  { href: CONTACTS.telegram, label: "Telegram" },
  { href: CONTACTS.vk, label: "ВКонтакте" },
].filter((link) => link.href !== "");
