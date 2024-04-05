# Throttle

A small client-server utility, that throttles commands sent to it from multiple
async sources. Also doubles as an error-notification handler for these jobs.

Features:

- if receiving multiple instances of an already running command, only one other instance will be executed, after the current one finishes, by running each command in it's own process
- allows chaining commands, each command in the chain is still correctly throttled
- repeats failed commands in configurable intervals
- configurable notification callback for failed commands
- configuration allows handling spammed notifications from flaky commands (e.g because of flaky networks)
- regex based on the fly rewrite of commands
- statistics on the amount of throttling

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
throttle-server
```

And send a command to the server (via unix socket):

```
throttle mbsync inbox
```

`throttle` should now run `mbsync inbox` for you. If you spam the above command
a couple of hundred times before the first one finishes, `throttle` will queue
up a single other instance of `mbsync inbox` after the first one finished.


## Usage

### Server

```
usage: throttle-server [-h] [--LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

start the throttle server

options:
  -h, --help            show this help message and exit
  --LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set loglevel.
```

### Client

```
usage: throttle [-h] [--version] [-j JOB] [-J SILENT_JOB] [-k] [-o ORIGIN] [--statistics] [--status] [--format {text,csv,latex,html,json,markdown,plain}]

send jobs to the throttle server

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -j JOB, --job JOB     Explicitly give job to execute, can be given multiple times, in that case, they will be run consecutively.
  -J SILENT_JOB, --silent-job SILENT_JOB
                        Same as --job, but no notifications will be sent on failure.
  -k, --kill            Kill a previously started job.
  -o ORIGIN, --origin ORIGIN
                        Set the origin of the message, which might be useful in tracking logs.
  --statistics          Print statistics for handled commands.
  --status              Print status information for currently running workers.
  --format {text,csv,latex,html,json,markdown,plain}
                        Format for printing results.
```

### Step-by-step and examples

First start a server with `throttle-server`. It will log to
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

The silent jobs can be used to check for prerequisite of commands. E.g. after moving a message locally one might run:

```
throttle \
  --job "notmuch new" \
  --silent-job "testinternetconnection" \
  --job "mbsync personal-inbox" \
  --job "notmuch new"
```

This first syncs the notmuch database locally, then checks for internet
connectivity (see
[this](https://github.com/ferdinandyb/dotfiles/blob/master/bin/testinternetconnection)
for an example), which will silently continue to be checked until internet is
back, then after internet is back, sync the local folder with the server and
finally run notmuch again to include the changes pulled from the server.

## Configuration

Configuration happens in `$XDG_CONFIG/throttle/config.toml`.

Example config:

```
task_timeout = 30
retry_sequence = [5,15,30,60,120,300,900]
retry_sequence_silent = [5,15,30,60]
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
- `retry_sequence`: list of seconds to successively wait if a (non-silent) job fails (e.g. bad credentials), the last element is retried in perpetuity
- `retry_sequence_silent`: list of seconds to successively wait if a silent job fails (e.g. no internet connection), the last element is retried in perpetuity
- `notification_cmd`: in case of a command failure, this command is called. See below for template keys
- `notify_on_counter`: how many failures before a notification should be sent
- `job_timeout`: how many seconds to let a job run, before timeouting it
- filters: each `filters` section defines a specific transformation, the first matching one is applied. `pattern` is checked against the command and if it matches, replaced by `substitute` using regex substitution (python `re.sub({pattern},{substitute},{input})` is used). In case of multiple commands in one call, it is done per command separately.

Key that can be used in `notification_cmd`:

- job: a job (single `--job`)
- urgency: this is always "urgent" for now
- errcode: errorcode if it exists (set to -1000 if error code was not returned)
- msg: usually stderr of subprocess

## Statistics

Running `throttle --statistics --format=markdown` will output something like
this. If connected to a tty, the job names will be truncated to make each row
fit on a line. When redirected, there's not truncating.

The column are the following (statistics are gathered from starting the server
and are not persisted across sessions):

- `run`: number of times the job has been actually run
- `total`: number of times the job has been submitted for running
- `throttle`: ratio of requests that were requested, but did not run
- `avg/min`: average number of `run` per minute

```
| job                               | run | total | throttle | avg/min |
| :---------------------------------| :-: | :---: | :------: | :-----: |
| mbsync priestoferis-folders       |  18 |  216  |   0.92   |   0.03  |
| mbsync priestoferis-inbox         |  10 |   37  |   0.73   |   0.02  |
| mbsync priestoferis-sent          |  10 |   36  |   0.72   |   0.02  |
| mbsync priestoferis-drafts        |  10 |   36  |   0.72   |   0.02  |
| mbsync priestoferis-archive       |  10 |   36  |   0.72   |   0.02  |
| mbsync elte-folders               |  72 |  144  |   0.50   |   0.13  |
| notmuch new                       | 832 |  1118 |   0.26   |   1.46  |
| mbsync elte-sent                  |  31 |   37  |   0.16   |   0.05  |
| mbsync elte-inbox                 |  44 |   49  |   0.10   |   0.08  |
| testinternetconnection            | 992 |  1080 |   0.08   |   1.74  |

```
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
