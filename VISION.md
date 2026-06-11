# SmartCart — Vision

## North Star

> Every small business runs on supplies. No one should spend hours a week manually ordering them.

SmartCart is the AI procurement co-pilot for small businesses — starting with daycares. It watches what you buy, finds the best deals, and places the order. You approve. That's it.

---

## Hackathon Scope (What We're Shipping)

Three features, one demo, three minutes.

**Feature 1 — Intelligent Product Selection**  
Not just "find the cheapest." Weighs quality (stars × review count), price (unit cost), and active deals. Bumps quantity when BOGO or bulk deals make stocking up smarter than buying one.

**Feature 2 — Coupon Discovery**  
Searches the web for promo codes before touching the cart. Applies the best one automatically. Even a 5% discount on a recurring order compounds over months.

**Feature 3 — Browser Automation**  
A real browser opens, navigates Walmart, adds items, applies coupons, and stops at the cart. The human approves. No surprise charges.

---

## Hackathon Success Criteria

| Criterion | Target |
|---|---|
| Live demo runs without crashing | Required |
| Feature 1 reasons out loud (shows product + deal logic) | Required |
| Browser visibly adds ≥2 items to Walmart cart | Required |
| Cart summary prints with total and savings | Required |
| Demo fits in 3 minutes | Required |
| Feature 2 finds or attempts ≥1 coupon | Nice to have |
| Zero hardcoded product choices (fully dynamic) | Required |

---

## Non-Goals (Hackathon)

- Multi-store price comparison (Target, Costco, Amazon) — post-hackathon
- Completing checkout / entering payment — intentionally excluded
- Building a coupon database — web search snippets are sufficient
- Frontend UI — terminal + live browser IS the demo
- Automated reorder schedules — mention in pitch, don't build
- Authentication / account management

---

## Post-Hackathon Roadmap

These are the slides you wave at during the "vision" section of the pitch. Do not build any of this at the hackathon.

**V2 — Multi-Store**  
Compare prices across Walmart, Target, Costco, Amazon. Buy from whichever is cheapest + fastest delivery.

**V3 — Calendar-Aware Ordering**  
Connect Google Calendar. Daycare has a "parent volunteer day" Friday → agent proactively orders snacks and plates on Tuesday.

**V4 — Reorder Intelligence**  
Learn consumption patterns. 12-pack of paper towels lasts 3 weeks → auto-draft a reorder 4 days before runout.

**V5 — Budget Management**  
Monthly spend reports. Alerts when a category goes over budget. Export to QuickBooks.

**V6 — Team Workflows**  
Staff submits a supply request → manager approves in one tap → agent executes. Full audit trail.

---

## The 30-Second Pitch

*"Small businesses like daycares spend hours every week manually ordering supplies — browsing store websites, comparing prices, hunting for coupons. We built an AI agent that does all of it. You say what you need, it finds the best deal, and shows up at checkout with a cart pre-loaded and a promo code already applied. You approve. Done."*
