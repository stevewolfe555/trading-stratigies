<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Volume distribution at each price level per time bucket
        Schema::create('volume_profile', function (Blueprint $table) {
            $table->timestampTz('bucket'); // Time bucket (1m, 5m, etc)
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->double('price_level');
            $table->bigInteger('total_volume')->default(0);
            $table->bigInteger('buy_volume')->default(0);  // Estimated from upticks
            $table->bigInteger('sell_volume')->default(0); // Estimated from downticks
            $table->integer('trade_count')->default(0);
            $table->primary(['bucket', 'symbol_id', 'price_level']);
        });

        DB::statement("SELECT create_hypertable('volume_profile', 'bucket', if_not_exists => TRUE);");
        DB::statement("CREATE INDEX IF NOT EXISTS idx_volume_profile_symbol ON volume_profile(symbol_id, bucket DESC);");

        // Computed metrics (POC, VAH, VAL, LVNs) per time bucket
        Schema::create('profile_metrics', function (Blueprint $table) {
            $table->timestampTz('bucket');
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->double('poc')->nullable(); // Point of Control (highest volume price)
            $table->double('vah')->nullable(); // Value Area High (top 70% volume)
            $table->double('val')->nullable(); // Value Area Low (bottom 70% volume)
            $table->bigInteger('total_volume')->default(0);
            $table->json('lvns')->nullable(); // Low Volume Nodes (gaps)
            $table->json('hvns')->nullable(); // High Volume Nodes (peaks)
            $table->primary(['bucket', 'symbol_id']);
        });

        DB::statement("SELECT create_hypertable('profile_metrics', 'bucket', if_not_exists => TRUE);");
    }

    public function down(): void
    {
        Schema::dropIfExists('profile_metrics');
        Schema::dropIfExists('volume_profile');
    }
};
