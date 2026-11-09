export const FEATURES = [
  { icon: "✦", title: "AI Business Agent", text: "An intelligent AI assistant that answers customer questions, understands requests and supports your business around the clock." },
  { icon: "▦", title: "Products & Services", text: "Manage products, services, menus, pricing, stock and availability. Your AI agent uses your approved business information." },
  { icon: "↗", title: "Smart Order Management", text: "Collect customer orders, confirm details, check delivery eligibility and send requests directly to your business dashboard." },
  { icon: "◎", title: "Customer Conversations", text: "Manage customer enquiries, conversation history, follow-ups and human handovers from one place." },
  { icon: "♙", title: "Team & Staff Management", text: "Organize employees, assign responsibilities and manage access with role-based permissions." },
  { icon: "⌁", title: "Business Analytics", text: "Monitor orders, enquiries, customer activity and business performance with centralized insights." },
];

/* Detailed groups for the Features page */
export const FEATURE_GROUPS = [
  {
    icon: "✦",
    title: "AI customer agent",
    intro: "Answers customers using only the information your business has approved.",
    points: [
      "Understands everyday, natural-language messages",
      "Answers from your menu, services, prices, timings, policies and FAQs",
      "Asks follow-up questions when details are missing",
      "Says when it cannot confirm something and shares your support contact",
    ],
  },
  {
    icon: "↗",
    title: "Orders & requests",
    intro: "From first message to confirmed order, all in your dashboard.",
    points: [
      "Checks options, prices and availability before taking an order",
      "Confirms the full summary and total with the customer first",
      "Routes orders to the right team, such as kitchen staff",
      "Prints order slips with items, quantities and instructions",
    ],
  },
  {
    icon: "⌖",
    title: "Delivery & service areas",
    intro: "Only accept orders you can actually fulfil.",
    points: [
      "Set your own delivery zones, cities, distance limits and fees",
      "Addresses outside your area are politely declined",
      "Checks the delivery address, not just the customer's city or country",
    ],
  },
  {
    icon: "✧",
    title: "Smart recommendations",
    intro: "Helpful suggestions from your real catalogue, never pushy.",
    points: [
      "Suggests add-ons and alternatives that are in stock",
      "Explains briefly why an option is suggested",
      "Never adds an item without the customer's confirmation",
      "Uses cautious wording on health topics and never gives medical advice",
    ],
  },
  {
    icon: "◎",
    title: "Conversations & human handover",
    intro: "Your team can step in whenever a person is needed.",
    points: [
      "Full conversation history for every customer",
      "Complaints, urgent issues and requests for a human are escalated",
      "Employees take over with the full context, so customers do not repeat themselves",
      "Escalation status and resolution are recorded",
    ],
  },
  {
    icon: "▦",
    title: "Business knowledge",
    intro: "You stay in control of what your agent knows.",
    points: [
      "Add products, prices, stock, hours, policies and FAQs",
      "Review and approve suggested knowledge updates",
      "The agent never changes prices, stock or policies on its own",
    ],
  },
  {
    icon: "♙",
    title: "Team & roles",
    intro: "The right access for every person on your team.",
    points: [
      "Create roles that fit your business, such as cashier, kitchen or support",
      "Employees only see what is relevant to their role",
      "Assign orders and tasks to a team or an individual",
    ],
  },
  {
    icon: "⌁",
    title: "Notifications & insights",
    intro: "Keep customers informed and see how your business is doing.",
    points: [
      "Order status updates: received, accepted, preparing, dispatched, delivered",
      "Choose which updates are sent and which channel is used",
      "Order volume, enquiry volume and common customer requests",
    ],
  },
];

export const SECURITY_POINTS = [
  { icon: "⛨", title: "Separate business data", text: "Each business has its own isolated data, users, orders and conversations." },
  { icon: "♙", title: "Role-based access", text: "Owners, managers and employees only see what their role allows." },
  { icon: "▤", title: "Audit logs", text: "Important admin actions and access to sensitive records are recorded." },
  { icon: "✓", title: "You approve the facts", text: "Prices, stock, policies and hours change only when you change them." },
];

export const STEPS = [
  { number: "01", title: "Register Your Business", text: "Create your account and select your business category." },
  { number: "02", title: "Configure Your Workspace", text: "Add your products, services, business information, team and operating rules." },
  { number: "03", title: "Activate Your AI Agent", text: "Your agent uses your approved business knowledge to assist your customers." },
  { number: "04", title: "Manage & Grow", text: "Monitor conversations, orders, requests and daily operations from your dashboard." },
];

/* Longer step details for the How It Works page */
export const STEP_DETAILS = [
  {
    number: "01",
    title: "Register your business",
    text: "Create your account, verify your email and tell us what kind of business you run.",
    points: ["Owner and business details", "CNIC and photo documents for verification", "Business category selection"],
  },
  {
    number: "02",
    title: "Set up your workspace",
    text: "Your workspace is created for your business category, with the right dashboard and terminology.",
    points: ["Locations, hours and contact details", "Delivery or service areas", "Products, services, prices and availability", "Policies and FAQs", "Team members and roles"],
  },
  {
    number: "03",
    title: "Activate your AI agent",
    text: "Your agent learns from the information you approved and is ready to talk to customers.",
    points: ["Share your unique business link right away", "Optionally connect WhatsApp or your website", "Set your support phone or email for handovers"],
  },
  {
    number: "04",
    title: "Manage and grow",
    text: "Orders and enquiries arrive in your dashboard, and your team takes it from there.",
    points: ["Confirm, route and print orders", "Take over conversations when needed", "Review insights and approve knowledge updates"],
  },
];

export const ORDER_FLOW = [
  "A customer opens your link or messages your business.",
  "The agent answers questions using your current menu and prices.",
  "It asks about size, quantity, add-ons and delivery or collection.",
  "The delivery address is checked against your service area.",
  "The customer confirms the order summary and total.",
  "The order appears on your dashboard and goes to the right team.",
  "The customer receives status updates until delivery.",
];

export const INDUSTRIES = [
  { icon: "♨", name: "Restaurants & Cafes", text: "Menu, orders, kitchen workflow and delivery status." },
  { icon: "▣", name: "Retail & E-commerce", text: "Product questions, availability and customer orders." },
  { icon: "✧", name: "Salons & Beauty", text: "Service information, pricing and customer requests." },
  { icon: "✚", name: "Hospitals & Clinics", text: "Enquiries, appointment requests and patient support." },
  { icon: "⌂", name: "Hotels & Hospitality", text: "Guest questions, service requests and information." },
  { icon: "➜", name: "Logistics & Delivery", text: "Delivery requests, areas and status updates." },
  { icon: "▤", name: "Schools & Academies", text: "Admission enquiries, schedules and parent questions." },
  { icon: "◉", name: "Gyms & Fitness", text: "Membership enquiries, timings and class information." },
  { icon: "⚙", name: "Service Businesses", text: "Service requests, quotes and customer follow-ups." },
  { icon: "▥", name: "Professional Services", text: "Client enquiries, consultation requests and FAQs." },
];

export const BENEFITS = [
  "Automate repetitive customer interactions",
  "Provide customer support around the clock",
  "Manage orders and requests centrally",
  "Keep your team organized and connected",
  "Make informed decisions with business insights",
  "Focus more on customers and business growth",
];

export const CHANNELS = [
  { icon: "◉", title: "WhatsApp", text: "Connect your WhatsApp Business channel." },
  { icon: "⌘", title: "Your Website", text: "Add an AI chat widget to your website." },
  { icon: "↗", title: "Shareable Link", text: "Share your unique business AI agent link." },
];

export const PLAN_FEATURES = [
  "AI-powered business agent",
  "Products and services management",
  "Customer conversations and enquiries",
  "Order and request management",
  "Employee and role management",
  "Business dashboard and insights",
  "Shareable AI business link",
];

export const FAQS = [
  {
    q: "What is included in the plan?",
    a: "Everything listed above: your AI agent, catalogue management, conversations, orders, team roles, dashboard insights and a shareable business link.",
  },
  {
    q: "When does billing start?",
    a: "Your first month is free after your business is approved, and no credit card is needed for the trial. After the free month the subscription renews at the listed monthly price unless you cancel.",
  },
  {
    q: "Do I need WhatsApp or a website?",
    a: "No. Integrations are optional. Your shareable business link works on its own, on mobile and desktop.",
  },
  {
    q: "Can my employees have limited access?",
    a: "Yes. You assign roles and permissions, so each employee sees only what is relevant to their work.",
  },
  {
    q: "Can other businesses see my data?",
    a: "No. Every business has separate data, users, orders and conversations.",
  },
];