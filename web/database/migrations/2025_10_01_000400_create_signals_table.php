<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('signals', function (Blueprint $table) {
            $table->timestampTz('time')->useCurrent();
            $table->foreignId('strategy_id')->nullable()->constrained('strategies');
            $table->foreignId('symbol_id')->nullable()->constrained('symbols');
            $table->string('type');
            $table->json('details')->nullable();
            $table->primary(['time', 'strategy_id', 'symbol_id']);
        });

        // Convert to hypertable and add index
        DB::statement("SELECT create_hypertable('signals', 'time', if_not_exists => TRUE);");
        DB::statement("CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol_id, time DESC);");
    }

    public function down(): void
    {
        Schema::dropIfExists('signals');
    }
};
