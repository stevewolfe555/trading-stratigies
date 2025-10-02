<?php

namespace App\Events;

use Illuminate\Broadcasting\Channel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class CandleTicked implements ShouldBroadcastNow
{
    use Dispatchable, SerializesModels;

    public function __construct(
        public string $symbol,
        public string $time,
        public float $close,
    ) {}

    public function broadcastOn(): array
    {
        return [new Channel('candles.' . $this->symbol)];
    }

    public function broadcastAs(): string
    {
        return 'candle.ticked';
    }

    public function broadcastWith(): array
    {
        return [
            'symbol' => $this->symbol,
            'time' => $this->time,
            'close' => $this->close,
        ];
    }
}
