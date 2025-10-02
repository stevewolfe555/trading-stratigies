<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class TimescaleBaselineSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        // Seed baseline symbols
        DB::table('symbols')->upsert([
            ['symbol' => 'AAPL', 'name' => 'Apple Inc.', 'exchange' => 'NASDAQ'],
        ], ['symbol']);

        // Seed sample SMA strategy
        $definition = json_encode([
            'type' => 'price_above_sma',
            'period' => 20,
            'symbol' => 'AAPL',
            'signal' => 'BUY',
        ]);

        DB::table('strategies')->upsert([
            ['name' => 'AAPL SMA20 Breakout', 'definition' => $definition, 'active' => true],
        ], ['name'], ['definition', 'active']);
    }
}
