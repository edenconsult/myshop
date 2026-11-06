# 12 — Accounts and roles

## What this is for

This is the list of everyone who is allowed to open the shop. When you take on a new cashier you add them
here, when one of them forgets their password you set a new one here, when someone changes their phone
number you correct it here, and when someone leaves you close their door here rather than deleting the
history they left behind. Only the owner ever sees this screen.

## You need

- **The owner seat (ADMIN).** Every action on this screen belongs to the owner. A cashier does not get the
  menu item at all, and typing the address as a cashier lands on the sign-in page — the same page a dead
  session shows, so it never looks like a refusal.
- **The screen: Accounts.** Open the account menu at the top right of any screen — the round badge with
  your initials — and choose **Manage accounts**. It is the only entry point; nothing else in the shop
  links here.
- **Data that must already exist:** nothing beyond the accounts themselves. The roster lists every account
  in the shop, newest created first, including ones that have never signed in and ones that have been shut.
- **The other person's cooperation, for one step only.** You cannot change your own password from here;
  that is *Change password* in the same menu, where you must type the old one (chapter 01).

## Steps

Two frames: the roster, and the dialog that adds somebody to it.

Both frames are pre-write. No account was created, edited, reset or deactivated while this manual was
photographed, so no frame here shows any of those results — each one is described in words, in the
shop's own phrasing, and said plainly as such.

![The Accounts screen: the heading "Accounts" over the line "Everyone who can sign in. Only you can manage
them.", a green "Add salesperson" button at the top right, and a table of five labelled columns — NAME,
USERNAME, ROLE, STATUS, LAST LOGIN — plus an unlabelled actions column at the right, holding four rows.
Each row shows a name, a login handle, a role in capitals, a green "Active" pill and a last-login date and
time. Three of the four rows carry the three action links "Edit details", "Reset password" and a rose
"Deactivate"; one row's action area is blank.](img/12-accounts/12-accounts.png)

**1. Read the roster.**

`NAME` is the person's first and last name. Where those were never recorded, the column falls back to the
login handle instead — three of the four rows in the frame are accounts created outside this screen, so
their `NAME` and `USERNAME` columns read the same word. `ROLE` is one of two words in capitals, `SALEPERSON`
or `ADMIN`; there is no third. `STATUS` is a green `Active` pill or a grey `Inactive` one. `LAST LOGIN` is
the shop's own date and time format, and reads a plain `—` for anyone who has not signed in yet. Rows are
ordered newest account first, not alphabetically, so a person you added this morning sits at the top.

**2. Notice which row has no buttons.**

In the frame, three rows end with `Edit details`, `Reset password` and `Deactivate`, and one row ends with
nothing at all. The blank row is your own. Two of those three things have a place of their own for you:
*Your profile* and *Change password* in the account menu, where they belong to the person using them. The
third has no place anywhere — the shop offers nobody a way to switch their own door off. The menu holds no
such entry, the roster hides the link on your own row, and if the request is forced in anyway the shop
refuses it. Nobody closes your account but whoever owns the shop.

**3. Add a cashier.**

Press `Add salesperson` at the top right. The dialog opens over the dimmed roster, and Cancel or the cross
in its corner closes it again without saving.

![The Add salesperson dialog, centred over the dimmed roster: a green plus tile beside the heading "Add
salesperson" and the line "New accounts sign in as salespersons; roles are not chosen here."; below, five
empty labelled boxes in the order USERNAME, FIRST NAME, LAST NAME, PASSWORD, PASSWORD CONFIRMATION; at the
bottom right, a plain "Cancel" button beside a green "Create account" button.](img/12-accounts/12-add-salesperson.png)

Fill all five boxes. Both names are asked for and both are kept: that is why a row added through this
dialog shows a person's name in the `NAME` column while the `USERNAME` column shows the handle they will
type to sign in.

`Create account` is where this step ends. No account was created while these pictures were taken, so no
frame shows what comes next. What the button does, in words: the roster reloads with the new person at the
top of it, and a green line appears above the table reading `<username> can sign in now.` Their `STATUS`
pill is green from the start, and their `LAST LOGIN` reads a plain `—` until they first sign in. Hand that
person their handle and password; they can use the till immediately.

**4. Correct someone's details.**

`Edit details` on their row opens a dialog headed `Edit details` with the line `For <username>. The username
and role do not change here.` It holds four boxes — `FIRST NAME`, `LAST NAME`, `EMAIL`, `TELEPHONE` — and
`Cancel` and `Save details`. Use this when a cashier changes their number, not the till or the ledger.

`Save details` is where this step ends. Nobody was edited while these pictures were taken, so there is no
frame of the result. In words: the dialog closes and a green line appears above the table reading
`Details saved for <username>.`, and that row's `NAME` column shows the new name the moment the roster
redraws. The handle and the role do not move, whatever you typed.

**5. Set a password for someone who has forgotten theirs.**

`Reset password` opens a dialog headed `Reset password` with `For <username>. They sign in with the new
password right away.` Two boxes — `New password` and `Confirm password` — then `Cancel` and `Save password`.
You are not asked for the old password and you cannot see it.

`Save password` is where this step ends. No password was reset while these pictures were taken, so the
result is in words only: the page reloads and a green line above the table reads
`New password saved for <username>.` The new password works at the very next sign-in — and any window that
person already had open stops working at the same moment, because the shop checks the session against the
password on every request. Expect them to be asked to sign in again, and tell them before you press
`Save password`.

**6. Close someone's door.**

`Deactivate` at the right of a row is a plain button, not a link that opens a dialog, and it takes effect
the moment you click it — there is no confirmation step. That click is where this step ends. Every row in
the frame is still green and still reads `Deactivate`, because nobody was switched off while these pictures
were taken; there is no frame of the other state. What you get, in words: the roster reloads, that row's
pill is now a grey `Inactive`, and the button has become a green `Reactivate`, which opens the door again
just as quickly. The person stays on the roster, and every receipt they rang up stays exactly where it was.

## When it goes wrong

- **The three buttons are simply not on your own row.** No disabled control, no note — the action area is
  blank. If someone forces the request in anyway, the shop answers with a bare page carrying one of three
  sentences: `Use Your profile for your own account.`, `Use Change password for your own account.`, and
  `You cannot deactivate your own account.` Those are the guard rails, and the blank row is what they look
  like from the outside.
- **A new account is refused if either name is missing.** `FIRST NAME` and `LAST NAME` are both required;
  leaving one empty puts Django's own `This field is required.` under that box and creates nothing. The
  dialog stays open with what you typed still in it.
- **A weak or mismatched password is refused, and the two dialogs refuse it differently.** In the add
  dialog, two different entries answer Django's own words under `PASSWORD CONFIRMATION` —
  `The two password fields didn’t match.` — and a password the shop's rules dislike is refused in the
  rules' own words under that same box: too short, too common, entirely numeric, or too close to that
  person's own name or handle. The reset dialog puts neither of them beside a box: both come back as
  a rose band across the top of the dialog, above the boxes, reading `The two password entries do not
  match.` for a mismatch or the rule's own sentence for a weak one — and it only runs either check when
  both of its boxes are filled, so a single entry is asked for the missing partner, never judged. Either
  refusal reopens the dialog it came from with what you typed still in it, and the reset dialog reopens on
  the same row.
- **A telephone number that is too long never gets that far.** The box will not take an eleventh
  character. The field is ten characters long and the browser is told so, so the keystroke does nothing and
  a pasted number is cut down to the first ten as it lands. No message appears, and no red text under
  `TELEPHONE`: the shop's own refusal could only fire on a value the box would not let you submit. The one
  place the limit is written down is *Your profile*, which prints `Up to 10 digits.` under the same box;
  this dialog prints nothing, so the box itself is the only teacher.
- **A deactivated account is refused at the door, and it looks exactly like a wrong password.** The
  sign-in page answers `Username or password is incorrect!` whether the password was wrong or the account
  was shut — and the same page is what a dead session shows. A cashier who says "my password stopped
  working" has, more often than not, been deactivated or has been sitting on an expired session. Ask which
  it is; the screen will not tell you.
- **There is no self-service way back in.** The shop sends no email whatsoever, has no forgotten-password
  page and no reset link. A cashier locked out after hours stays locked out until the owner is physically
  at a keyboard with this screen open.
- **A cashier cannot reach this screen, and is not told so.** They land on the sign-in page with no
  message, which is the shape chapter 01 explains as the shop's single answer to "you may not see that".

## Notes & limits

- **Roles are not chosen here and cannot be changed here.** Every account created on this screen is a
  salesperson, whatever the person who made it intended — the dialog says as much:
  `New accounts sign in as salespersons; roles are not chosen here.` Nothing on this screen promotes a
  cashier to owner or demotes an owner.
- **No account is ever deleted.** Deactivating is the strongest thing this screen does. The row remains on
  the roster, its receipts remain in the orders ledger and the reports, and a deactivated person still
  appears in the cashier dropdowns on both of those screens — which is correct, because their history still
  needs filtering.
- **A login handle cannot be renamed.** Not here, not on *Your profile*, not anywhere a shop user can
  reach. Choose it carefully in the dialog.
- **Two roles, and nothing in between.** There is no per-screen permission list, no "reports only" cashier,
  no second owner with narrower rights. A cashier either works the till or does not.
- **What a cashier can never reach:** the owner's hub, *Products & Stock*, the orders ledger, the sales
  reports, and this screen. Their entire working world is the till and their own receipts (chapters 08 and
  09), and the takings figure at the top of the till, which reads `Your Takings` for them and
  `Today's Takings` for the owner.
- **Django's built-in administration area exists on this install, and it is not a shop workflow.** It will
  let someone set a role, delete an account outright, or overwrite a password behind the shop's own rules.
  It is a developer's break-glass tool for fixing what the screens cannot do, and it is deliberately not
  taught here; if you find yourself needing it, that is a gap to raise with whoever maintains the shop, and
  chapter 13 keeps the list.
- **The roster is a snapshot, not a register of attendance.** `LAST LOGIN` is the last successful sign-in
  only; it says nothing about who is standing at the till now, and it does not update while a session stays
  open.
- **Nothing here is checked against the receipts.** Deactivating a cashier who has an unfinished sale in an
  open cart does not stop that cart; it stops the next sign-in.
- **The roster shows five labelled columns, plus an unlabelled actions column at the right, and it keeps
  two facts off them.** An account's email address and telephone number are stored and editable, but they
  only appear inside the `Edit details` dialog — the table itself will never show them, so you cannot audit
  a phone list at a glance.
- **The add dialog has no role box, no email box and no "generate a password" option.** Email belongs to
  `Edit details`, and the password is whatever you type: the shop never mails a credential to anyone, and
  there is no suggested password to hand over.

Related chapters: 01 (your own account, your own password, what a bounced session looks like), 08 (what a
salesperson can do once they are in), 10 and 11 (where the cashier names on this roster reappear as
filters), 13 (what the shop still does not have for people management).
