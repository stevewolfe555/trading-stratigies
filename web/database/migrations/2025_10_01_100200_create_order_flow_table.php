<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Order flow metrics per time bucket
        Schema::create('order_flow', function (Blueprint $table) {
            $table->timestampTz('bucket');
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->bigInteger('delta')->default(0); // buy_volume - sell_volume
            $table->bigInteger('cumulative_delta')->default(0); // Running CVD
            $table->bigInteger('aggressive_buys')->default(0);
            $table->bigInteger('aggressive_sells')->default(0);
            $table->double('buy_pressure')->default(0); // % of volume that was buying
            $table->double('sell_pressure')->default(0); // % of volume that was selling
            $table->primary(['bucket', 'symbol_id']);
        });

        DB::statement("SELECT create_hypertable('order_flow', 'bucket', if_not_exists => TRUE);");
        DB::statement("CREATE INDEX IF NOT EXISTS idx_order_flow_symbol ON order_flow(symbol_id, bucket DESC);");
    }

    public function down(): void
    {
        Schema::dropIfExists('order_flow');
    }
};
