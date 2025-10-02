<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ticks', function (Blueprint $table) {
            $table->timestampTz('time');
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->double('price');
            $table->bigInteger('size');
            $table->string('exchange', 10)->nullable();
            $table->primary(['time', 'symbol_id', 'price']);
        });

        // Convert to hypertable for time-series optimization
        DB::statement("SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE);");
        DB::statement("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks(symbol_id, time DESC);");
        
        // Add compression policy (compress data older than 1 day)
        DB::statement("
            ALTER TABLE ticks SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'symbol_id'
            );
        ");
        DB::statement("
            SELECT add_compression_policy('ticks', INTERVAL '1 day', if_not_exists => TRUE);
        ");
    }

    public function down(): void
    {
        Schema::dropIfExists('ticks');
    }
};
