<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Schedule;
use Carbon\Carbon;
use Predis\Client as PredisClient;
use App\Events\CandleTicked;
use App\Events\SignalEmitted;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Artisan::command('signals:notify', function () {
    $email = env('NOTIFY_EMAIL');
    if (!$email) {
        $this->comment('NOTIFY_EMAIL not set; skipping notifications');
        return 0;
    }

    $since = Cache::get('signals_notify_since');
    if (!$since) {
        $since = Carbon::now('UTC')->subMinutes(5);
    } else {
        $since = Carbon::parse($since);
    }

    $rows = DB::select(
        'SELECT s.time, sy.symbol, st.name AS strategy_name, s.type, s.details
         FROM signals s
         LEFT JOIN symbols sy ON sy.id = s.symbol_id
         LEFT JOIN strategies st ON st.id = s.strategy_id
         WHERE s.time > ?
         ORDER BY s.time ASC
         LIMIT 50',
        [$since]
    );

    if (!$rows) {
        $this->comment('No new signals since '.$since->toDateTimeString().'Z');
        return 0;
    }

    $lines = array_map(function ($r) {
        $time = Carbon::parse($r->time)->toIso8601String();
        $details = is_string($r->details) ? $r->details : json_encode($r->details);
        return sprintf('%s | %s | %s | %s | %s', $time, $r->symbol, $r->strategy_name, $r->type, $details);
    }, $rows);

    $body = "New trading signals (".count($rows)."):\n".implode("\n", $lines);
    Mail::raw($body, function ($m) use ($email) {
        $m->to($email)->subject('New Trading Signals');
    });

    $last = end($rows)->time;
    Cache::put('signals_notify_since', $last, now()->addHours(24));

    $this->info('Notifications sent to '.$email);
    return 0;
})->purpose('Send email notifications for new signals');

// Schedule the notifications every minute (requires: php artisan schedule:work)
Schedule::command('signals:notify')->everyMinute();

// Redis -> Reverb relay to broadcast real-time events
Artisan::command('relay:redis', function () {
    $host = env('REDIS_HOST', '127.0.0.1');
    $port = (int) env('REDIS_PORT', 6380);
    $this->info("Connecting to Redis at {$host}:{$port}...");

    $redis = new PredisClient([
        'host' => $host,
        'port' => $port,
        // Prevent read timeout for blocking pub/sub loop
        'read_write_timeout' => 0,
        // Optional connect timeout
        'timeout' => 5.0,
    ]);

    $pubsub = $redis->pubSubLoop();
    $pubsub->subscribe('ticks:candles');
    $pubsub->subscribe('signals');

    foreach ($pubsub as $message) {
        if (!isset($message->kind) || $message->kind !== 'message') {
            continue;
        }
        $channel = $message->channel ?? '';
        $payload = json_decode($message->payload ?? '{}', true) ?: [];

        if ($channel === 'ticks:candles') {
            $symbol = (string) ($payload['symbol'] ?? '');
            $time = (string) ($payload['time'] ?? now()->toIso8601String());
            $close = (float) ($payload['close'] ?? 0);
            event(new CandleTicked($symbol, $time, $close));
        } elseif ($channel === 'signals') {
            $symbol = (string) ($payload['symbol'] ?? '');
            $time = (string) ($payload['time'] ?? now()->toIso8601String());
            $type = (string) ($payload['type'] ?? 'UNKNOWN');
            $strategy = $payload['strategy'] ?? null;
            $details = $payload['details'] ?? null;
            event(new SignalEmitted($symbol, $time, $type, $strategy, $details));
        }
    }
})->purpose('Relay Redis pub/sub messages to Reverb broadcast events');
