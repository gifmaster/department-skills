# Breach notification templates and Datatilsynet form checklist
Use: read when drafting the notice to affected individuals (Art. 34), writing the internal breach log entry (Art. 33(5)) or preparing the facts for Datatilsynet's online breach form.

Legal information and drafting support, not legal advice. Involve the DPO (if any) and a lawyer for high-risk breaches. Replace all [placeholders].

## Key rules

| Rule | Value | Source |
|---|---|---|
| Notify Datatilsynet | Without undue delay and where feasible within 72 hours of becoming aware, unless the breach is unlikely to result in a risk to individuals; give reasons for any delay | GDPR Art. 33(1) |
| Processor | Notify the controller without undue delay | GDPR Art. 33(2) |
| Phased notification | Information may be provided in phases without further undue delay | GDPR Art. 33(4) |
| Internal documentation | Document every breach: facts, effects and remedial action, whether notified or not | GDPR Art. 33(5) |
| Notify individuals | Without undue delay if likely high risk to their rights and freedoms | GDPR Art. 34(1) |
| Content of notice to individuals | Clear and plain language: nature of the breach; name and contact details of DPO or other contact point; likely consequences; measures taken or proposed, including to mitigate effects | GDPR Art. 34(2), referring to Art. 33(3)(b), (c), (d) |
| No notice needed to individuals if | (a) data was unintelligible to others, e.g. encrypted; (b) later measures mean the high risk is no longer likely; (c) it would involve disproportionate effort (then a public communication instead) | GDPR Art. 34(3) |
| Danish specifics | CPR numbers have special rules (databeskyttelsesloven § 11); NIS2 or DORA may require separate, faster incident reports for in-scope entities | databeskyttelsesloven; SKILL.md |

## 1. Notice to affected individuals

Send by the channel the person normally uses with you (email, Digital Post, letter). For employees, consider a personal conversation first, then the written notice. Do not include more personal data in the notice than needed.

### Danish (du-form)

> Emne: Vigtig information om dine personoplysninger
>
> Kære [navn]
>
> Vi skriver til dig, fordi der er sket et brud på sikkerheden omkring nogle af dine personoplysninger. Vi beklager det meget.
>
> **Hvad er der sket?**
> Den [dato] [kort og konkret beskrivelse, fx "blev en fil med lønoplysninger ved en fejl sendt til en forkert e-mailmodtager uden for virksomheden" / "fik en uvedkommende adgang til vores kundesystem"]. Vi opdagede det den [dato].
>
> **Hvilke oplysninger drejer det sig om?**
> [Fx dit navn, din adresse, dit CPR-nummer, dit kontonummer og din løn.] [Hvis relevant: Det drejer sig ikke om [fx adgangskoder / helbredsoplysninger].]
>
> **Hvad kan det betyde for dig?**
> [Konkret vurdering, fx "Der er en risiko for, at oplysningerne kan misbruges til identitetstyveri, fx ved forsøg på at optage lån i dit navn." / "Vi vurderer, at risikoen for misbrug er lav, fordi modtageren har bekræftet skriftligt, at filen er slettet."]
>
> **Hvad har vi gjort?**
> - [Fx bedt modtageren slette filen og fået skriftlig bekræftelse]
> - [Fx lukket adgangen og skiftet adgangskoder]
> - [Fx anmeldt bruddet til Datatilsynet den [dato]] [og til politiet]
> - [Fx indført advarsel ved e-mails til eksterne modtagere]
>
> **Hvad kan du gøre?**
> - [Fx være opmærksom på e-mails, sms'er eller opkald, hvor nogen beder om personlige oplysninger eller betaling]
> - [Fx holde øje med dine kontobevægelser og kontakte din bank ved mistænkelige transaktioner]
> - [Fx overveje at få registreret en kreditadvarsel hos et kreditoplysningsbureau (verify current options)]
> - [Fx skifte adgangskode, hvis du bruger den samme andre steder]
>
> **Spørgsmål**
> Du er velkommen til at kontakte [navn / databeskyttelsesrådgiver] på [e-mail] eller [telefon], hvis du har spørgsmål.
>
> Du har ret til at klage til Datatilsynet, datatilsynet.dk.
>
> Venlig hilsen
> [Navn, titel]
> [Virksomhed]

### English

> Subject: Important information about your personal data
>
> Dear [name],
>
> We are writing to tell you about a security incident affecting some of your personal data. We are very sorry this has happened.
>
> **What happened?**
> On [date] [short, specific description, e.g. "a file containing payroll details was sent by mistake to the wrong external email recipient" / "an unauthorised person gained access to our customer system"]. We discovered this on [date].
>
> **What information is involved?**
> [e.g. your name, address, CPR number, bank account number and salary.] [If relevant: It does not include [e.g. passwords / health information].]
>
> **What could this mean for you?**
> [Specific assessment, e.g. "There is a risk that the information could be misused for identity fraud, such as attempts to take out loans in your name." / "We consider the risk of misuse to be low because the recipient has confirmed in writing that the file has been deleted."]
>
> **What have we done?**
> - [e.g. asked the recipient to delete the file and obtained written confirmation]
> - [e.g. closed the access and changed passwords]
> - [e.g. notified Datatilsynet on [date]] [and the police]
> - [e.g. introduced a warning for emails to external recipients]
>
> **What can you do?**
> - [e.g. be alert to emails, texts or calls asking for personal details or payment]
> - [e.g. monitor your bank account and contact your bank about suspicious transactions]
> - [e.g. change your password if you use the same one elsewhere]
>
> **Questions**
> Please contact [name / data protection officer] at [email] or [phone] if you have any questions.
>
> You have the right to complain to the Danish Data Protection Agency (Datatilsynet), datatilsynet.dk.
>
> Kind regards,
> [Name, title]
> [Organisation]

### Notice checklist (Art. 34(2))

- [ ] Nature of the breach described in clear and plain language
- [ ] Name and contact details of the DPO or other contact point
- [ ] Likely consequences for the individual
- [ ] Measures taken or proposed, including steps the individual can take
- [ ] No jargon, no blame on individuals, no more personal data than needed
- [ ] Danish for Danish recipients; English or other language where the recipient uses it

## 2. Internal breach log entry (Art. 33(5))

Log every breach, including those not notified. Keep the reasoning for each decision.

| Field | Entry |
|---|---|
| Breach ID | [YYYY-nnn] |
| Logged by / date | [name] / [date] |
| Date and time breach occurred (or estimate) | [ ] |
| Date and time of awareness (72-hour clock start) | [ ] |
| How discovered and by whom | [ ] |
| Description of what happened | [ ] |
| Type of breach | [confidentiality / integrity / availability] |
| Cause | [human error / technical / malicious / physical / unknown] |
| Systems and locations involved | [ ] |
| Categories of personal data | [ ] |
| Special categories (Art. 9), criminal data (Art. 10), CPR numbers | [yes/no, which] |
| Categories of data subjects | [employees / customers / minors / patients / other] |
| Number of data subjects (exact or estimate) | [ ] |
| Number of records (exact or estimate) | [ ] |
| Processor or other parties involved | [ ] |
| Containment measures and time taken | [ ] |
| Likely consequences for individuals | [ ] |
| Risk assessment: likelihood / severity / overall | [low / medium / high] with reasons |
| Decision on notifying Datatilsynet, with reasons | [yes / no] |
| Date and time notified, reference number | [ ] |
| Reasons for any delay beyond 72 hours | [ ] |
| Decision on notifying individuals, with reasons (incl. any Art. 34(3) ground relied on) | [ ] |
| Date and method of notice to individuals | [ ] |
| Other notifications (police, bank, NIS2 or DORA authority, insurer, customers as controllers) | [ ] |
| Remedial and preventive actions, owner, deadline | [ ] |
| DPO advice | [ ] |
| Closed date and sign-off | [ ] |

## 3. Datatilsynet online form: fields to prepare (verify)

Danish breach notifications are submitted through the joint breach reporting solution on virk.dk, which routes the report to Datatilsynet (and to other authorities if selected). The list below is based on the virk.dk user guide for the personal data breach form, not the live form; fields and order may change (verify on datatilsynet.dk before use).

Prepare these answers before you open the form:

- [ ] **Reporter**: name; whether this is a supplement to an earlier report (and its reference)
- [ ] **Organisation**: CVR, name, department, address, contact person (name, title, email, phone), internal reference number
- [ ] **Reporting on behalf of another organisation** (for example a processor reporting for the controller): yes or no, and which
- [ ] **Data protection officer**: whether there is one; name, email, phone
- [ ] **Type of incident and authorities**: personal data breach under GDPR; Datatilsynet selected (plus other authorities if relevant, for example under NIS2)
- [ ] **Course of events and causes**: description; human, physical or technical causes; type of security breach; type of incident (for example human error)
- [ ] **Personal data affected**: tick list such as name, contact details, CPR number, financial data, location data, health data, biometric or genetic data, other, not yet known
- [ ] **Scope**: categories of persons affected (employees, customers, patients, children, citizens and so on); number of persons; whether the number is an estimate
- [ ] **Cross-border**: whether persons in other EU/EEA countries are affected; which countries and how many
- [ ] **Timeline**: date and time of discovery and how discovered; when the breach started and how; whether it is ongoing; when and how it ended
- [ ] **Reason for late notification** if more than 72 hours after awareness
- [ ] **Other parties involved**: processors or subcontractors (yes, no, do not know)
- [ ] **Handling**: measures taken to stop the breach and by whom; measures planned to prevent recurrence; measures in place before the breach
- [ ] **Notification of data subjects**: done, will be done, public communication due to disproportionate effort, undecided pending investigation, or will not be done; date, method, sender and the text of the notice
- [ ] **Download a copy** of the submitted report: the user guide states data in the system is deleted after a period (30 days per the guide, verify)

Tips:
- Notify within 72 hours even if facts are incomplete; mark the report as preliminary and supplement it later (Art. 33(4)).
- Use the internal log above as the single source for both the form and the notice to individuals, so facts match.

## 4. Short holding statement for customers or staff (optional)

### Danish

> Vi er blevet opmærksomme på en hændelse, der kan have berørt personoplysninger om [gruppe]. Vi undersøger sagen og har [kort tiltag]. Berørte personer får direkte besked. Spørgsmål kan rettes til [kontakt].

### English

> We have become aware of an incident that may have affected personal data about [group]. We are investigating and have [brief action]. Those affected will be contacted directly. Questions can be sent to [contact].
