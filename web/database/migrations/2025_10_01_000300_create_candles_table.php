<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('candles', function (Blueprint $table) {
            $table->timestampTz('time');
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->double('open')->nullable();
            $table->double('high')->nullable();
            $table->double('low')->nullable();
            $table->double('close')->nullable();
            $table->bigInteger('volume')->nullable();
            $table->primary(['time', 'symbol_id']);
        });

        // Convert to hypertable and add index
        DB::statement("SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);");
        DB::statement("CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol_id, time DESC);");
    }

    public function down(): void
    {
        Schema::dropIfExists('candles');
    }
};
