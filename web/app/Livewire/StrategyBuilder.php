<?php

namespace App\Livewire;

use Illuminate\Support\Facades\DB;
use Livewire\Component;

class StrategyBuilder extends Component
{
    public string $name = '';
    public string $symbol = 'AAPL';
    public int $period = 20;
    public bool $active = true;
    public array $symbols = [];

    public function mount(): void
    {
        $this->symbols = DB::table('symbols')->orderBy('symbol')->pluck('symbol')->toArray();
        if (!$this->symbols) {
            $this->symbols = ['AAPL'];
        }
        if (!in_array($this->symbol, $this->symbols)) {
            $this->symbol = $this->symbols[0];
        }
    }

    public function save(): void
    {
        $this->validate([
            'name' => 'required|string|min:3',
            'symbol' => 'required|string',
            'period' => 'required|integer|min:1|max:1000',
            'active' => 'boolean',
        ]);

        $definition = [
            'type' => 'price_above_sma',
            'period' => $this->period,
            'symbol' => $this->symbol,
            'signal' => 'BUY',
        ];

        DB::table('strategies')->upsert([
            [
                'name' => $this->name,
                'definition' => json_encode($definition),
                'active' => $this->active,
            ]
        ],
        ['name'], // unique by name
        ['definition','active']); // update on conflict

        $this->dispatch('notify', message: 'Strategy saved.');
        $this->reset(['name', 'period', 'active']);
        $this->period = 20;
        $this->active = true;
    }

    public function toggle(int $id): void
    {
        $row = DB::table('strategies')->select('active')->where('id', $id)->first();
        if ($row) {
            DB::table('strategies')->where('id', $id)->update(['active' => !$row->active]);
        }
    }

    public function render()
    {
        $strategies = DB::table('strategies')->select('id','name','definition','active')->orderBy('name')->get()->map(function($r){
            $def = is_string($r->definition) ? json_decode($r->definition, true) : $r->definition;
            return [
                'id' => $r->id,
                'name' => $r->name,
                'active' => (bool)$r->active,
                'symbol' => $def['symbol'] ?? 'AAPL',
                'period' => $def['period'] ?? null,
                'type' => $def['type'] ?? null,
            ];
        });
        return view('livewire.strategy-builder', [
            'strategies' => $strategies,
        ]);
    }
}
