# Throttle

A small client-server utility, that throttles commands sent to it from multiple
async sources.

Features:

- if receiving multiple instances of an already running command, only one other instance will be executed, after the current one finishes, by running each command in it's own process
- allows chaining commands, each command in the chain is still correctly throttled
- repeats failed commands in configurable intervals
- configurable notification callback for failed commands
- configuration allows handling spammed notifications from flaky commands (e.g because of flaky networks)
- regex based on the fly rewrite of commands

## Social

Development and support happens on
[sourcehut](https://sr.ht/~ferdinandyb/throttle/), but there's a mirror on
[github](https://github.com/ferdinandyb/throttle) for convenience and
discoverability. You can also star there to show your interest/appreciation.

## Rationale

Although `throttle` doesn't care what you want to run with it, it was written
to solve issue's I had with syncing my email properly. It resolves the
following problems I had:

- Correct, on-demand, responsive syncing of a mail account with [mbsync](https://isync.sourceforge.io/):
  Instead of running `mbsync account-inbox` every X seconds (a waste of
  resources), I trigger the command via hooks in [aerc](https://aerc-mail.org/)
  whenever I make an operation in my inbox, or via
  [goimapnotify](https://gitlab.com/shackra/goimapnotify) when something changes
  on the server. Sync `mbsync` locks the folder it operates on, running multiple
  instances of `mbsync account-inbox` could leave you with a half-synced state.
  Practical example is receiving 10 emails in a short time: that's 10 triggers
  from `goimapnotify`, but only the first couple of emails will be synced.
  `goimapnotify`'s [wait](https://gitlab.com/shackra/goimapnotify/-/issues/10)
  setting sacrifices responsiveness and still doesn't guarantee a correctly
  synced state.
- Remapping aerc hooks running `mbsync $AERC_ACCOUNT-$AERC_FOLDER` to the correct `mbsync` channel.
- Every sync operation with `mbsync` needs to be followed up by a `notmuch new`,
  but `notmuch` also locks when running, which could lead to inconsistency
  between a `maildir` and a `notmuch` view of my emails. Chaining them via
  `throttle` makes sure `notmuch new` is executed after each `mbsync` operation,
  but only as much as actually needed.

- Executing `notify-send` in sync scripts after every failure was annoying to
  set up and quite spammy when connections got flaky (which is always when
  resuming from a sleep). Those executions were also "lost". Throttle will
  retry and can be configured to only send a notification on the second
  failure, which in practice has removed the spam alltogether.


## Getting started

Install with

```
pipx install git+https://git.sr.ht/~ferdinandyb/throttle
```

Start server with

```
throttle --server
```

And send a command to the server (via unix socket):

```
throttle mbsync inbox
```

`throttle` should now run `mbsync inbox` for you. If you spam the above command
a couple of hundred times before the first one finishes, `throttle` will queue
up a single other instance of `mbsync inbox` after the first one finished.


## Usage

```
usage: throttle [-h] [-s | -j JOB] [-k] [-o ORIGIN] [--LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

options:
  -h, --help            show this help message and exit
  -s, --server          Start server.
  -j JOB, --job JOB     Explicitly give job to execute, can be given multiple times, in that case, they will be run consecutively.
  -k, --kill            Kill a previously started job.
  -o ORIGIN, --origin ORIGIN
                        Set the origin of the message, which might be useful in tracking logs.
  --LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set loglevel.
```

First start a server with `throttle --server`. It will log to
`$XDG_STATE/throttle/throttle.log`, which should default to
`~/.local/state/throttle/throttle.log`.

To start a job run `throttle my command` which will run `my command`. You can
make it explicit by running `throttle --job "my command"`. Multiple `--job`
flags will execute the command successively. Any dangling parameters will be
scooped up for a last command so

```
throttle hello --job "my command" world
```

is equivalent to

```
throttle --job "my command" --job "hello world"
```

although you probably should not do this. Anyhow, this will first execute `my
command` and if it succeeds, it will run then run `hello world`. When running
multiple commands, they are executed serially.

If one `throttle --job "hello world"` errors out and you don't want it to run
indefinitely, you can stop it alltogether by `throttle --kill --job "hello
world"`. Note, that this does not save you from restarting it with `throttle
--job "hello world"` again.

Practical usage of a multiple commands would be something like:

```
throttle --job "mbsync personal-inbox" --job "notmuch new"
```

## Configuration

Configuration happens in `$XDG_CONFIG/throttle/config.toml`.

Example config:

```
task_timeout = 30
retry_sequence = [5,15,30,60,120,300,900]
notification_cmd = 'notify-send --urgency={urgency} --app-name="throttle" "{job} ({origin})" "({errcode}): {msg}"'

notify_on_counter = 2
job_timeout = 600

[[filters]]
pattern = '^sleep \d$'
substitute = "sleep 10"

[[filters]]
pattern = '^sleep \d\d'
substitute = "sleep 15"

[[filters]]
pattern = '^mbsync (\w+)-(?!(inbox|archive|sent|drafts)$).+'
substitute = 'mbsync \1-folders'
```

- `task_timeout`: how long to wait before cleaning up a process with no more incoming commands (probably no need to change this)
- `retry_sequence`: list of seconds to successively wait if a command fails (e.g. no internet connection), the last element is retried in perpetuity
- `notification_cmd`: in case of a command failure, this command is called. See below for template keys
- `notify_on_counter`: how many failures before a notification should be sent
- `job_timeout`: how many seconds to let a job run, before timeouting it
- filters: each `filters` section defines a specific transformation, the first matching one is applied. `pattern` is checked against the command and if it matches, replaced by `substitute` using regex substitution (python `re.sub({pattern},{substitute},{input})` is used). In case of multiple commands in one call, it is done per command separately.

Key that can be used in `notification_cmd`:

- job: a job (single `--job`)
- urgency: this is always "urgent" for now
- errcode: errorcode if it exists (set to -1000 if error code was not returned)
- msg: usually stderr of subprocess

## Troubleshooting

### pinentry on frequent gpg access

If the command you are running requires gpg, and after multiple commands you are being asked for a pinentry, although normally your gpg key is unlocked, you need to add something like this to `gpg-agent.conf`:

```
auto-expand-secmem 100
```

### executables not found when started with systemd

Systemd can load PATH from many places, including some that are not available
immediately on startup. The easiest way to solve this is using
[environment.d](https://www.freedesktop.org/software/systemd/man/latest/environment.d.html),
but you might need to make sure that your file comes _after_ `environment` when
sorted alphabetically. See
[here](https://github.com/ferdinandyb/dotfiles/blob/master/.config/environment.d/README.md)
for a bit more detail.

## Contributing and issues

Please send patches to
[~ferdinandyb/throttle-devel@lists.sr.ht](mailto:~ferdinandyb/throttle-devel@lists.sr.ht)
(see https://git-send-email.io/ on how to do that). You can set up your repository by running:

```
git config format.subjectPrefix "PATCH throttle"
git config sendemail.to "~ferdinandyb/throttle-devel@lists.sr.ht"
git config format.notes true
git config notes.rewriteRef refs/notes/commits
git config notes.rewriteMode concatenate
```

You can also send questions to this list (note, that list.sr.ht does not
delivier emails with attachments or text/html parts, see
https://useplaintext.email/ on setting up your client for sending only in
text/plain). Open tickets on https://todo.sr.ht/~ferdinandyb/throttle.

Considering the amount of interaction I expect, I will also not bite for github
PR-s and github issues, but my preferences are the above.
