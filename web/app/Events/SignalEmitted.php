<?php

namespace App\Events;

use Illuminate\Broadcasting\Channel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class SignalEmitted implements ShouldBroadcastNow
{
    use Dispatchable, SerializesModels;

    public function __construct(
        public string $symbol,
        public string $time,
        public string $type,
        public ?string $strategy = null,
        public array|string|null $details = null,
    ) {}

    public function broadcastOn(): array
    {
        return [new Channel('signals')];
    }

    public function broadcastAs(): string
    {
        return 'signal.emitted';
    }

    public function broadcastWith(): array
    {
        return [
            'symbol' => $this->symbol,
            'time' => $this->time,
            'type' => $this->type,
            'strategy' => $this->strategy,
            'details' => $this->details,
        ];
    }
}
