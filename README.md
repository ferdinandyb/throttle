# Throttle

A small client-server utility, that throttles commands sent to it from multiple
sources, by making sure that if a specific command is sent multiple times,
while the first instance is running, it is executed once _after_ the first
command finished. Can be configured to map commands together by regex matching.

## Social

Development and support happens on
[sourcehut](https://sr.ht/~ferdinandyb/throttle/), but there's a mirror on
[github](https://github.com/ferdinandyb/throttle) for convenience and
discoverability. You can also star there to show your interest/appreciation.

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

## Why?


You sync your email with `mbsync` and want things to be responsive, but you
don't want to run `mbsync inbox` every second no matter what is happening. So
you set up an imap notification service to run `mbsync inbox` on every new mail
and you set up your MUA to also run the same every time you do an operation in
your Inbox. All's good, but you now get a patch series with 10 emails, so the
first `mbsync inbox` is still running when all the other instances are started.
The instances started later recognize the lock by the first and silently exit,
leaving you with only about 5 out of 10 emails. Running it through `throttle`
will makes sure that after the first `mbsync inbox` a second one is executed
_after_ the first one finished, so you get all of the emails. You can run into
a similar problem when quickly archiving mail from you inbox: many `mbsync`
commands triggered in succession, but only really the first couple of
operations synced by `mbsync`.

## Usage

```
usage: throttle [-h] [-s | -c CMD | -k]
                [--LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

options:
  -h, --help            show this help message and exit
  -s, --server          Start server.
  -c CMD, --cmd CMD     Explicitly give cmd to execute, can be given multiple
                        times, in that case, they will be run consecutively.
  -k, --kill            Kill a previously started cmd.
  --LOGLEVEL {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set loglevel.
```

First start a server with `throttle --server`. It will log to
`$XDG_STATE/throttle/throttle.log`, which should default to
`~/.local/state/throttle/throttle.log`.

To start a job run `throttle my command` which will run `my command`. You can make it explicit by running `throttle --cmd "my command"`. Multiple `--cmd` flags will execute the command successively, if they all succeed with exit code 0. Any dangling parameters will be scooped up for a last command so

```
throttle hello --cmd "my command" world
```

is equivalent to

```
throttle --cmd "my command" --cmd "hello world"
```

although you probably should not do this. Anyhow, this will first execute `my
command` and if it succeeds, it will run then run `hello world`. When running
multiple commands, they are treated as one call in terms of throttling.

If one `throttle --cmd "hello world"` errors out and you don't want it to run
indefinitely, you can stop it alltogether by `throttle --kill --cmd "hello
world"`. Note, that this does not save you from restarting it with `throttle
--cmd "hello world"` again.

Practical usage of a multiple commands would be something like:

```
throttle --cmd "mbsync inbox" --cmd "notmuch new"
```

## Configuration

Configuration happens in `$XDG_CONFIG/throttle/config.toml`.

Example config:

```
task_timeout = 30
retry_sequence = [5,15,30,60,120,300,900]
notification_cmd = 'notify-send --urgency={urgency} --app-name="{key} (throttle)" "{job}" "{errcode}: {msg}"'
notify_on_counter = 2
job_timeout = 600

[[filters]]
regex = '^sleep \d$'
result = "sleep 10"

[[filters]]
regex = '^sleep \d\d'
result = "sleep 15"

```

- `task_timeout`: how long to wait before cleaning up a process with no more incoming commands (probably no need to change this)
- `retry_sequence`: list of seconds to successively wait if a command fails (e.g. no internet connection), the last element is retried in perpetuity
- `notification_cmd`: in case of a command failure, this command is called. See below for template keys
- `notify_on_counter`: how many failures before a notification should be sent
- `job_timeout`: how many seconds to let a job run, before timeouting it
- filters: each `filters` section defines a specific transformation, the first matching one is applied. `regex` is checked against the command and if it matches, replaced by `result` verbatim. In case of multiple commands in one call, it is done per command separately.

Key that can be used in `notification_cmd`:

- key: references the entire command that started the jobs (multiple `--cmd`-s)
- job: a job (single `--cmd`)
- urgency: this is always "urgent" for now
- errcode: errorcode if it exists (set to -1000 if error code was not returned)
- msg: usually stderr of subprocess

## Contributing and issues

Please send patches to
[~ferdinandyb/throttle-devel@lists.sr.ht](mailto:~ferdinandyb/throttle-devel@lists.sr.ht)
(see https://git-send-email.io/ on how to do that). You can also send questions
here (note, that list.sr.ht does not delivier emails with attachments or
text/html parts, see https://useplaintext.email/ on setting up your client for
sending only in text/plain). Open tickets on
https://todo.sr.ht/~ferdinandyb/throttle. Considering the amount of interaction
I expect, I will also not bite for github PR-s and github issues, but my
preferences are the above.
