<?php

namespace App\Livewire;

use Illuminate\Support\Facades\DB;
use Livewire\Component;

class SignalsLog extends Component
{
    public array $rows = [];
    public int $limit = 50;

    protected function loadData(): void
    {
        $sql = <<<SQL
        SELECT s.time, sy.symbol, st.name as strategy_name, s.type, s.details
        FROM signals s
        LEFT JOIN symbols sy ON sy.id = s.symbol_id
        LEFT JOIN strategies st ON st.id = s.strategy_id
        ORDER BY s.time DESC
        LIMIT ?
        SQL;
        $this->rows = array_map(function($r) {
            return [
                'time' => (new \DateTime($r->time))->format('Y-m-d H:i:s'),
                'symbol' => $r->symbol,
                'strategy' => $r->strategy_name,
                'type' => $r->type,
                'details' => is_string($r->details) ? $r->details : json_encode($r->details),
            ];
        }, DB::select($sql, [$this->limit]));
    }

    public function render()
    {
        $this->loadData();
        return view('livewire.signals-log');
    }
}
