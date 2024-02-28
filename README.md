# Throttle

A small client-server utility, that throttles commands sent to it from multiple
sources, by making sure that if a specific command is sent multiple times,
while the first instance is running, it is executed once _after_ the first
command finished. Can be configured to map commands together by regex matching.

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

## Configuration

Configuration happens in `$XDG_CONFIG/throttle/config.toml`.

Example config:

```
task_timeout = 30
retry_sequence = [5,15,30,60,120,300,900]
notification_cmd = 'echo "code:{errcode} stdout:{stdout} stdin:{stderr}"'

[[filters]]
regex = '^sleep \d$'
result = "sleep 10"

[[filters]]
regex = '^sleep \d\d'
result = "sleep 15"
```

- `task_timeout`: how long to wait before cleaning up a process with no more incoming commands (probably no need to change this)
- `retry_sequence`: list of seconds to successively wait if a command fails (e.g. no internet connection), the last element is retried in perpetuity (TODO: this is probably a bad idea)
- `notification_cmd`: in case of a command failure, this command is called, while `{errcode}`, `{stdout}` and `{stderr}` being replaced with the eponymous outputs.
- filters: each `filters` section defines a specific transformation, the first matching one is applied. `regex` is checked against the command and if it matches, replaced by `result` verbatim.


# TODO:

- switch from print to proper logging
- add some help to CLI
