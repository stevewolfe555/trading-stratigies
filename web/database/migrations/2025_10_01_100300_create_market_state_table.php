<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Market state detection (Balance vs Imbalance)
        Schema::create('market_state', function (Blueprint $table) {
            $table->timestampTz('time');
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->string('state', 20); // 'BALANCE', 'IMBALANCE_UP', 'IMBALANCE_DOWN'
            $table->double('balance_high')->nullable();
            $table->double('balance_low')->nullable();
            $table->double('poc')->nullable(); // Current POC
            $table->double('confidence')->default(0); // 0-1 confidence score
            $table->primary(['time', 'symbol_id']);
        });

        DB::statement("SELECT create_hypertable('market_state', 'time', if_not_exists => TRUE);");
    }

    public function down(): void
    {
        Schema::dropIfExists('market_state');
    }
};
