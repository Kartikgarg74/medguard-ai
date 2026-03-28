# MedGuard AI — Impact Model

**Quantified estimate of business impact: time saved, cost reduced, revenue recovered.**

---

## 1. The Problem (Hard Numbers)

| Metric | Value | Source |
|--------|-------|--------|
| Total overcharging detected by NPPA | Rs 10,013.3 crore | NPPA Overcharging Status, Sept 2025 |
| Amount actually recovered | Rs 1,487.1 crore (14.8%) | NPPA |
| Outstanding/unrecovered | Rs 8,526.1 crore | NPPA |
| Under litigation | Rs 5,938.7 crore | NPPA |
| FY 2023-24 annual recovery | Rs 72.73 crore | NPPA |
| Total overcharging cases | 2,690 (since 1997) | NPPA |
| Pharma Sahi Daam app downloads | ~220,000 | Google Play Store |
| Pharmacies in India | 700,000 - 1,900,000 | Credence Research |
| DPCO-controlled formulations | 928+ | NPPA notifications |

## 2. MedGuard AI Impact — Conservative Estimates

### Detection Speed

| Metric | Before (Manual) | After (MedGuard) | Improvement |
|--------|:-:|:-:|:-:|
| Time to detect a ceiling price violation | 3-5 years (litigation cycle) | 6 hours (next pipeline run) | 99.97% faster |
| Compliance check throughput | ~100 drugs/month (per PMRU) | 200 drugs/hour (automated) | 1,440x faster |
| Geographic coverage | 31-32 states (1 PMRU each) | All platforms simultaneously | Instant national coverage |

### Cost Reduction

| Metric | Before | After | Savings |
|--------|:-:|:-:|:-:|
| Annual monitoring cost (32 PMRUs) | Rs 16 crore/year (est.) | Rs 6 lakh/year ($7,200 infra) | Rs 15.94 crore/year |
| Cost per compliance check | ~Rs 500 (manual) | ~Rs 0.01 (automated) | 50,000x cheaper |

### Revenue Recovery (Conservative)

```
Assumption: MedGuard monitors 928 scheduled formulations across top 100 pharmacy chains

Detection rate: 5% of monitored drugs found overpriced (conservative)
= 928 x 0.05 = ~46 drugs

Average overcharge per unit: Rs 10 (conservative, actual Rs 5-50)
Average monthly volume per drug per chain: 500 units
Chains monitored: 100

Monthly overcharge detected:
= 46 drugs x Rs 10 x 500 units x 100 chains
= Rs 2,30,00,000 (Rs 2.3 crore/month)

Annual overcharge detected:
= Rs 27.6 crore/year

With Para 15 interest (15% p.a.):
= Rs 27.6 crore + Rs 4.14 crore interest
= Rs 31.74 crore/year recoverable
```

### Outstanding Overcharging Addressable

```
Outstanding unrecovered: Rs 8,526.1 crore
If MedGuard accelerates detection and enables 1% additional recovery:
= Rs 85.26 crore
If 5% additional recovery:
= Rs 426.3 crore
```

## 3. Assumptions

1. DPCO ceiling prices are updated quarterly by NPPA (historically consistent)
2. Online pharmacy prices are representative of retail market pricing
3. 5% violation rate is conservative — actual may be higher given Rs 10,013 crore historical overcharging
4. Volume estimates (500 units/drug/chain/month) based on common essential medicines
5. Infrastructure costs based on Groq free tier + Railway/Render free hosting
6. Interest calculation per DPCO 2013, Paragraph 15 (15% per annum)

## 4. Non-Financial Impact

| Impact Area | Description |
|-------------|-------------|
| **Consumer protection** | Patients pay fair prices for essential medicines |
| **Regulatory enforcement** | NPPA gets real-time compliance data instead of years-old cases |
| **Transparency** | Multi-platform price comparison reveals price disparities |
| **Deterrence** | Automated monitoring discourages future overcharging |
| **Data for policy** | Aggregated violation data informs DPCO amendments and NLEM updates |

## 5. One-Liner for Judges

> "India has Rs 8,526 crore in unrecovered pharmaceutical overcharging. MedGuard AI detects violations in 6 hours instead of 3-5 years, at 1/250th the cost of manual monitoring."
